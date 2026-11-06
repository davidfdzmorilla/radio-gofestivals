"""watchdog · periodic health checks that alert through Telegram.

Meant to run from cron every ~15 min (`check`) plus once a day (`summary`).
Container facts come from the host (`docker inspect`, see
infra/deploy/watchdog.sh) because this container has no Docker socket.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import typer
from sqlalchemy import text

from scripts.alerting import Alerter
from scripts.db import make_engine, make_sessionmaker
from scripts.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

log = get_logger("watchdog")
app = typer.Typer(help="radio.gofestivals · watchdog + Telegram alerts")

EXPECTED_CONTAINERS = (
    "radio-api-prod",
    "radio-web-prod",
    "radio-icy-worker-prod",
    "radio-postgres-prod",
    "radio-redis-prod",
)
# Alert when active stations fall below this fraction of the 7-day median.
CATALOG_DROP_RATIO = 0.8
# Below this baseline the catalog is too small for the ratio to mean anything.
CATALOG_MIN_BASELINE = 100
CATALOG_HISTORY_DAYS = 7
# health-check runs every 6h; two missed runs plus slack.
HEALTH_STALE_HOURS = 13.0
# Restarts since the previous watchdog run that count as a restart loop.
RESTART_LOOP_DELTA = 3

HISTORY_KEY = "watchdog:active_history"
RESTARTS_KEY = "watchdog:restarts:"


@dataclass(frozen=True)
class ContainerState:
    status: str
    health: str  # "none" when the image defines no healthcheck
    restarts: int


def parse_containers(raw: str) -> dict[str, ContainerState]:
    """Parse lines `name status health restart_count` (docker inspect -f)."""
    out: dict[str, ContainerState] = {}
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) != 4:  # noqa: PLR2004
            continue
        name, status, health, restarts = parts
        if restarts.isdigit():
            out[name.lstrip("/")] = ContainerState(status, health, int(restarts))
    return out


def container_problem(name: str, state: ContainerState | None) -> str | None:
    if state is None:
        return f"Contenedor {name} no encontrado"
    if state.status != "running":
        return f"Contenedor {name} en estado '{state.status}'"
    if state.health == "unhealthy":
        return f"Contenedor {name} unhealthy"
    return None


def restart_problem(name: str, state: ContainerState | None, prev: int | None) -> str | None:
    if state is None or prev is None:
        return None
    delta = state.restarts - prev
    if delta >= RESTART_LOOP_DELTA:
        return f"Contenedor {name} reiniciado {delta} veces desde la última comprobación"
    return None


def catalog_dropped(active: int, history: list[int]) -> bool:
    if not history:
        return False
    baseline = statistics.median(history)
    return baseline >= CATALOG_MIN_BASELINE and active < baseline * CATALOG_DROP_RATIO


async def _apply(alerter: Alerter, key: str, problem: str | None, ok_msg: str) -> None:
    if problem is not None:
        await alerter.send(key, problem)
    else:
        await alerter.resolve(key, ok_msg)


async def _catalog_counts(session: AsyncSession) -> dict[str, float]:
    row = (
        await session.execute(
            text(
                """
                SELECT
                    count(*) FILTER (WHERE status = 'active')   AS active,
                    count(*) FILTER (WHERE status = 'broken')   AS broken,
                    count(*) FILTER (WHERE status = 'inactive') AS inactive,
                    count(*) FILTER (WHERE created_at > now() - interval '24 hours') AS new_24h,
                    (SELECT EXTRACT(EPOCH FROM now() - max(last_check_at)) / 3600
                       FROM station_streams) AS health_age_h
                FROM stations
                """,
            ),
        )
    ).one()
    age = row.health_age_h
    return {
        "active": int(row.active),
        "broken": int(row.broken),
        "inactive": int(row.inactive),
        "new_24h": int(row.new_24h),
        "health_age_h": float(age) if age is not None else float("inf"),
    }


async def _load_history(alerter: Alerter) -> dict[str, int]:
    if alerter.store is None:
        return {}
    try:
        raw = await alerter.store.get(HISTORY_KEY)
        return {str(k): int(v) for k, v in json.loads(raw).items()} if raw else {}
    except Exception as exc:  # noqa: BLE001
        log.warning("history_unavailable", error_type=type(exc).__name__)
        return {}


async def _save_history(alerter: Alerter, history: dict[str, int]) -> None:
    if alerter.store is None:
        return
    keep = dict(sorted(history.items())[-CATALOG_HISTORY_DAYS:])
    try:
        await alerter.store.set(HISTORY_KEY, json.dumps(keep))
    except Exception as exc:  # noqa: BLE001
        log.warning("history_unavailable", error_type=type(exc).__name__)


async def run_check(alerter: Alerter, session: AsyncSession, containers_raw: str | None) -> None:
    counts = await _catalog_counts(session)
    active = int(counts["active"])

    # --- catalog drop (vs the median of previous days; today's sample excluded) ---
    today = datetime.now(UTC).date().isoformat()
    history = await _load_history(alerter)
    previous = [v for d, v in history.items() if d != today]
    dropped = catalog_dropped(active, previous)
    baseline = int(statistics.median(previous)) if previous else 0
    await _apply(
        alerter,
        "catalog_drop",
        f"Catálogo caído: {active} estaciones activas (mediana 7d: {baseline})"
        if dropped
        else None,
        f"Catálogo recuperado: {active} estaciones activas",
    )
    if not dropped:
        history[today] = active  # never learn the outage as the new normal
        await _save_history(alerter, history)

    # --- health-check not running / stale ---
    stale = counts["health_age_h"] > HEALTH_STALE_HOURS
    await _apply(
        alerter,
        "health_stale",
        f"Health-check sin ejecutarse desde hace {counts['health_age_h']:.0f} h" if stale else None,
        "Health-check de nuevo al día",
    )

    # --- containers ---
    if containers_raw is None:
        log.warning("containers_not_provided")
        return
    states = parse_containers(containers_raw)
    for name in EXPECTED_CONTAINERS:
        state = states.get(name)
        await _apply(
            alerter,
            f"container:{name}",
            container_problem(name, state),
            f"Contenedor {name} OK",
        )
        prev: int | None = None
        if alerter.store is not None and state is not None:
            try:
                raw = await alerter.store.get(RESTARTS_KEY + name)
                prev = int(raw) if raw is not None else None
                await alerter.store.set(RESTARTS_KEY + name, str(state.restarts))
            except Exception as exc:  # noqa: BLE001
                log.warning("restart_state_unavailable", error_type=type(exc).__name__)
        await _apply(
            alerter,
            f"restart:{name}",
            restart_problem(name, state, prev),
            f"Contenedor {name} estable",
        )


async def run_summary(alerter: Alerter, session: AsyncSession) -> None:
    c = await _catalog_counts(session)
    age = c["health_age_h"]
    age_txt = "nunca" if age == float("inf") else f"hace {age:.1f} h"
    await alerter.info(
        "radio.gofestivals · resumen diario\n"
        f"Activas: {int(c['active'])} · rotas: {int(c['broken'])} "
        f"· inactivas: {int(c['inactive'])}\n"
        f"Nuevas 24h: {int(c['new_24h'])}\n"
        f"Último health-check: {age_txt}",
    )


@app.command("check")
def cmd_check(
    containers: str = typer.Option(
        "",
        "--containers",
        help="Fichero con `name status health restarts` por línea; '-' = stdin",
    ),
) -> None:
    """Catalog drop, stale health-check and container state → Telegram."""
    raw: str | None = None
    if containers:
        raw = sys.stdin.read() if containers == "-" else open(containers, encoding="utf-8").read()  # noqa: SIM115,PTH123

    async def _main() -> None:
        engine = make_engine()
        maker = make_sessionmaker(engine)
        try:
            async with Alerter.from_env(required=True) as alerter, maker() as session:
                await run_check(alerter, session, raw)
        finally:
            await engine.dispose()

    asyncio.run(_main())


@app.command("summary")
def cmd_summary() -> None:
    """Send the daily one-line catalog summary."""

    async def _main() -> None:
        engine = make_engine()
        maker = make_sessionmaker(engine)
        try:
            async with Alerter.from_env(required=True) as alerter, maker() as session:
                await run_summary(alerter, session)
        finally:
            await engine.dispose()

    asyncio.run(_main())


@app.command("notify")
def cmd_notify(
    key: str = typer.Option(..., "--key", help="Dedup key, e.g. cron:rb_sync"),
    message: str = typer.Option(..., "--message"),
) -> None:
    """Send one deduplicated alert (used by infra/deploy/run-job.sh)."""

    async def _main() -> None:
        async with Alerter.from_env(required=True) as alerter:
            await alerter.send(key, message)

    asyncio.run(_main())


@app.command("resolve")
def cmd_resolve(
    key: str = typer.Option(..., "--key", help="Dedup key of the alert to close"),
    message: str = typer.Option(..., "--message"),
) -> None:
    """Send a recovery message, only if an alert for `key` is open."""

    async def _main() -> None:
        async with Alerter.from_env(required=True) as alerter:
            await alerter.resolve(key, message)

    asyncio.run(_main())


if __name__ == "__main__":
    app()
