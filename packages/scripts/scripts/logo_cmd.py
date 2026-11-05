"""fetch-logos · CLI command (ADR 011).

Descarga el `favicon` de cada emisora activa (URL guardada por `rb_sync`), lo procesa
(`logo_fetch`) y guarda dos copias WebP propias en `station_logos`, dejando el hash en
`stations.logo_hash` para que los listados sepan si hay logo. Pensado para correr cada
noche tras `rb_sync`; es idempotente: solo toca lo que toca (nuevo, URL cambiada,
reintento con backoff o refresco mensual).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx
import typer
from sqlalchemy import text

from scripts.db import make_engine, make_sessionmaker
from scripts.logging import get_logger
from scripts.logo_fetch import LogoFetchError, LogoRejectedError, ProcessedLogo, fetch_logo
from scripts.url_guard import guard_request

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

log = get_logger("fetch_logos")
app = typer.Typer(help="radio.gofestivals · descarga y procesa los logos de las emisoras")

# Reintentos tras un fallo transitorio: 1, 3, 7, 14 y luego 30 días.
BACKOFF_DAYS = (1, 3, 7, 14, 30)
REFRESH_DAYS = 30
# Hay hosts (i.ibb.co, postimg…) con decenas de logos nuestros: no se les abre una
# avalancha de conexiones.
PER_HOST_CONCURRENCY = 2
MAX_ERROR_LENGTH = 300


@dataclass(frozen=True)
class Candidate:
    station_id: uuid.UUID
    slug: str
    url: str
    previous_url: str | None
    previous_attempts: int


@dataclass
class Stats:
    ok: int = 0
    failed: int = 0
    rejected: int = 0


def backoff(attempts: int) -> timedelta:
    """Espera antes del siguiente intento tras `attempts` fallos seguidos (1 = el primero)."""
    return timedelta(days=BACKOFF_DAYS[min(max(attempts, 1), len(BACKOFF_DAYS)) - 1])


def build_client() -> httpx.AsyncClient:
    """Cliente con el guard SSRF en cada petición y redirección (ADR 008)."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=10.0),
        follow_redirects=True,
        max_redirects=3,
        limits=httpx.Limits(max_connections=20),
        event_hooks={"request": [guard_request]},
    )


async def select_candidates(
    session: AsyncSession,
    *,
    limit: int,
    slug: str | None = None,
) -> list[Candidate]:
    # Con `slug` se ignoran los plazos: sirve para forzar una emisora concreta.
    due = (
        ""
        if slug
        else """
        AND (
            l.station_id IS NULL
            OR l.source_url <> s.favicon_url
            OR (l.status = 'failed' AND l.next_retry_at <= now())
            OR (
                l.status = 'ok'
                AND l.fetched_at < now() - make_interval(days => :refresh_days)
                AND COALESCE(l.next_retry_at, now()) <= now()
            )
        )"""
    )
    only = "AND s.slug = :slug" if slug else ""
    params: dict[str, object] = {"limit": limit}
    if slug:
        params["slug"] = slug
    else:
        params["refresh_days"] = REFRESH_DAYS
    rows = (
        await session.execute(
            text(
                f"""
                SELECT s.id, s.slug, s.favicon_url, l.source_url, COALESCE(l.attempts, 0)
                FROM stations s
                LEFT JOIN station_logos l ON l.station_id = s.id
                WHERE s.favicon_url IS NOT NULL
                  AND s.status = 'active'
                  AND s.hidden = false
                  {only}
                  {due}
                ORDER BY (l.station_id IS NOT NULL), s.quality_score DESC, s.id
                LIMIT :limit
                """,  # noqa: S608
            ),
            params,
        )
    ).all()
    return [
        Candidate(
            station_id=uuid.UUID(str(r[0])),
            slug=str(r[1]),
            url=str(r[2]),
            previous_url=None if r[3] is None else str(r[3]),
            previous_attempts=int(r[4]),
        )
        for r in rows
    ]


async def _save_ok(session: AsyncSession, cand: Candidate, logo: ProcessedLogo) -> None:
    await session.execute(
        text(
            """
            INSERT INTO station_logos
                (station_id, source_url, status, content_hash, data_sm, data_lg,
                 attempts, last_error, checked_at, fetched_at, next_retry_at, updated_at)
            VALUES
                (:id, :url, 'ok', :hash, :sm, :lg, 0, NULL, now(), now(), NULL, now())
            ON CONFLICT (station_id) DO UPDATE SET
                source_url = EXCLUDED.source_url, status = 'ok',
                content_hash = EXCLUDED.content_hash,
                data_sm = EXCLUDED.data_sm, data_lg = EXCLUDED.data_lg,
                attempts = 0, last_error = NULL, checked_at = now(), fetched_at = now(),
                next_retry_at = NULL, updated_at = now()
            """,
        ),
        {
            "id": str(cand.station_id),
            "url": cand.url,
            "hash": logo.content_hash,
            "sm": logo.sm,
            "lg": logo.lg,
        },
    )
    await session.execute(
        text("UPDATE stations SET logo_hash = :hash WHERE id = :id"),
        {"id": str(cand.station_id), "hash": logo.content_hash},
    )


async def _save_failed(session: AsyncSession, cand: Candidate, error: str) -> None:
    same_url = cand.previous_url == cand.url
    attempts = cand.previous_attempts + 1 if same_url else 1
    # Con la misma URL, un refresco fallido conserva el logo válido que ya había; con una
    # URL nueva, el logo anterior ya no corresponde y se descarta.
    await session.execute(
        text(
            """
            INSERT INTO station_logos
                (station_id, source_url, status, attempts, last_error, checked_at,
                 next_retry_at, updated_at)
            VALUES
                (:id, :url, 'failed', :attempts, :err, now(), now() + :delay, now())
            ON CONFLICT (station_id) DO UPDATE SET
                status = CASE WHEN :same AND station_logos.status = 'ok'
                              THEN 'ok' ELSE 'failed' END,
                source_url = EXCLUDED.source_url,
                content_hash = CASE WHEN :same THEN station_logos.content_hash END,
                data_sm = CASE WHEN :same THEN station_logos.data_sm END,
                data_lg = CASE WHEN :same THEN station_logos.data_lg END,
                attempts = EXCLUDED.attempts, last_error = EXCLUDED.last_error,
                checked_at = now(), next_retry_at = EXCLUDED.next_retry_at,
                updated_at = now()
            """,
        ),
        {
            "id": str(cand.station_id),
            "url": cand.url,
            "attempts": attempts,
            "err": error[:MAX_ERROR_LENGTH],
            "delay": backoff(attempts),
            "same": same_url,
        },
    )
    if not same_url:
        await session.execute(
            text("UPDATE stations SET logo_hash = NULL WHERE id = :id"),
            {"id": str(cand.station_id)},
        )


async def _save_rejected(session: AsyncSession, cand: Candidate, error: str) -> None:
    await session.execute(
        text(
            """
            INSERT INTO station_logos
                (station_id, source_url, status, attempts, last_error, checked_at, updated_at)
            VALUES (:id, :url, 'rejected', 1, :err, now(), now())
            ON CONFLICT (station_id) DO UPDATE SET
                source_url = EXCLUDED.source_url, status = 'rejected',
                content_hash = NULL, data_sm = NULL, data_lg = NULL,
                attempts = 1, last_error = EXCLUDED.last_error, checked_at = now(),
                next_retry_at = NULL, updated_at = now()
            """,
        ),
        {"id": str(cand.station_id), "url": cand.url, "err": error[:MAX_ERROR_LENGTH]},
    )
    await session.execute(
        text("UPDATE stations SET logo_hash = NULL WHERE id = :id"),
        {"id": str(cand.station_id)},
    )


async def _process_one(
    client: httpx.AsyncClient,
    maker: async_sessionmaker[AsyncSession],
    cand: Candidate,
    stats: Stats,
    *,
    dry_run: bool,
) -> None:
    logo: ProcessedLogo | None = None
    outcome, error = "ok", ""
    try:
        logo = await fetch_logo(client, cand.url)
    except LogoRejectedError as exc:
        outcome, error = "rejected", str(exc)
    except LogoFetchError as exc:
        outcome, error = "failed", str(exc)
    except Exception as exc:  # noqa: BLE001 — un logo roto nunca debe tumbar el job
        outcome, error = "failed", f"unexpected {type(exc).__name__}: {exc}"
    log.debug("logo_result", slug=cand.slug, outcome=outcome, error=error or None)
    if outcome == "ok":
        stats.ok += 1
    elif outcome == "rejected":
        stats.rejected += 1
    else:
        stats.failed += 1
    if dry_run:
        return
    async with maker() as session:
        if logo is not None:
            await _save_ok(session, cand, logo)
        elif outcome == "rejected":
            await _save_rejected(session, cand, error)
        else:
            await _save_failed(session, cand, error)
        await session.commit()


async def process_candidates(
    maker: async_sessionmaker[AsyncSession],
    client: httpx.AsyncClient,
    candidates: list[Candidate],
    *,
    concurrency: int = 8,
    dry_run: bool = False,
) -> Stats:
    stats = Stats()
    global_sem = asyncio.Semaphore(concurrency)
    host_sems: defaultdict[str, asyncio.Semaphore] = defaultdict(
        lambda: asyncio.Semaphore(PER_HOST_CONCURRENCY),
    )

    async def run(cand: Candidate) -> None:
        host = urlparse(cand.url).hostname or ""
        async with global_sem, host_sems[host]:
            await _process_one(client, maker, cand, stats, dry_run=dry_run)

    await asyncio.gather(*(run(c) for c in candidates))
    return stats


@app.command()
def fetch_logos(
    dry_run: bool = typer.Option(
        default=False,
        help="Descarga y procesa, pero no escribe en la base de datos.",
    ),
    limit: int = typer.Option(
        default=3000,
        help="Máximo de emisoras a procesar en esta pasada.",
    ),
    concurrency: int = typer.Option(
        default=8,
        help="Descargas simultáneas (máx. 2 por host).",
    ),
    station: str | None = typer.Option(
        default=None,
        help="Slug concreto: ignora los plazos y vuelve a descargar su logo.",
    ),
) -> None:
    """Descarga y procesa los logos pendientes de las emisoras activas."""

    async def _main() -> None:
        engine = make_engine()
        maker = make_sessionmaker(engine)
        started = time.monotonic()
        try:
            async with maker() as session:
                candidates = await select_candidates(session, limit=limit, slug=station)
            log.info("fetch_logos_start", candidates=len(candidates), dry_run=dry_run)
            async with build_client() as client:
                stats = await process_candidates(
                    maker,
                    client,
                    candidates,
                    concurrency=concurrency,
                    dry_run=dry_run,
                )
            log.info(
                "fetch_logos_done",
                dry_run=dry_run,
                candidates=len(candidates),
                ok=stats.ok,
                failed=stats.failed,
                rejected=stats.rejected,
                seconds=round(time.monotonic() - started, 1),
            )
        finally:
            await engine.dispose()

    asyncio.run(_main())
