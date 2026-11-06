from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import httpx
import respx
from sqlalchemy import text
from typer.testing import CliRunner

from scripts import watchdog
from scripts.alerting import Alerter, AlertSettings
from scripts.watchdog import (
    EXPECTED_CONTAINERS,
    HISTORY_KEY,
    ContainerState,
    catalog_dropped,
    container_problem,
    parse_containers,
    restart_problem,
    run_check,
    run_summary,
)
from tests.test_alerting import FakeStore

if TYPE_CHECKING:
    import pytest
    from sqlalchemy.ext.asyncio import AsyncSession

URL = "https://api.telegram.org/bot123:SECRET/sendMessage"
SETTINGS = AlertSettings(token="123:SECRET", chat_id="42")  # noqa: S106


def _healthy_containers(**overrides: str) -> str:
    lines = []
    for name in EXPECTED_CONTAINERS:
        lines.append(overrides.get(name, f"{name} running healthy 0"))
    return "\n".join(lines)


def test_parse_containers_skips_garbage() -> None:
    parsed = parse_containers("/radio-api-prod running healthy 2\nbad line\nx running none abc\n")
    assert parsed == {"radio-api-prod": ContainerState("running", "healthy", 2)}


def test_container_problem_cases() -> None:
    assert container_problem("c", None) is not None
    assert container_problem("c", ContainerState("restarting", "none", 5)) is not None
    assert container_problem("c", ContainerState("running", "unhealthy", 0)) is not None
    assert container_problem("c", ContainerState("running", "none", 0)) is None
    assert container_problem("c", ContainerState("running", "healthy", 0)) is None


def test_restart_problem_needs_delta() -> None:
    st = ContainerState("running", "healthy", 10)
    assert restart_problem("c", st, None) is None  # first run: no baseline
    assert restart_problem("c", st, 9) is None
    assert restart_problem("c", st, 7) is not None


def test_catalog_dropped_thresholds() -> None:
    assert catalog_dropped(71, [1500, 1480, 1510]) is True
    assert catalog_dropped(1300, [1500, 1480, 1510]) is False  # -13%: normal churn
    assert catalog_dropped(0, []) is False  # no baseline yet
    assert catalog_dropped(5, [20, 30]) is False  # tiny catalog, ratio meaningless


async def _seed(
    db_session: AsyncSession, *, active: int, broken: int, checked_ago_h: float
) -> None:
    await db_session.execute(
        text(
            """
            INSERT INTO stations (slug, name, status)
            SELECT 's' || g, 'S' || g, (CASE WHEN g <= :a THEN 'active' ELSE 'broken' END)::station_status
            FROM generate_series(1, :n) g
            """,
        ),
        {"a": active, "n": active + broken},
    )
    await db_session.execute(
        text(
            """
            INSERT INTO station_streams (station_id, stream_url, is_primary, status, last_check_at)
            SELECT id, 'https://x.example/' || slug, true, 'active',
                   now() - make_interval(hours => :h)
            FROM stations
            """,
        ),
        {"h": checked_ago_h},
    )
    await db_session.commit()


def _sent_texts(route: respx.Route) -> list[str]:
    return [json.loads(c.request.read())["text"] for c in route.calls]


@respx.mock
async def test_check_alerts_on_catalog_drop_and_does_not_learn_it(
    db_session: AsyncSession,
) -> None:
    route = respx.post(URL).respond(200, json={"ok": True})
    await _seed(db_session, active=71, broken=1500, checked_ago_h=1)
    store = FakeStore()
    yesterday = (datetime.now(UTC) - timedelta(days=1)).date().isoformat()
    store.data[HISTORY_KEY] = json.dumps({yesterday: 1500})
    async with Alerter(SETTINGS, store=store, client=httpx.AsyncClient()) as a:
        await run_check(a, db_session, _healthy_containers())
    texts = _sent_texts(route)
    assert any("Catálogo caído" in t and "71" in t for t in texts)
    assert len(texts) == 1
    assert json.loads(store.data[HISTORY_KEY]) == {yesterday: 1500}  # 71 not recorded


@respx.mock
async def test_check_healthy_sends_nothing_and_records_history(db_session: AsyncSession) -> None:
    route = respx.post(URL).respond(200, json={"ok": True})
    await _seed(db_session, active=300, broken=10, checked_ago_h=1)
    store = FakeStore()
    async with Alerter(SETTINGS, store=store, client=httpx.AsyncClient()) as a:
        await run_check(a, db_session, _healthy_containers())
    assert route.call_count == 0
    assert list(json.loads(store.data[HISTORY_KEY]).values()) == [300]


@respx.mock
async def test_check_flags_stale_health_check_and_bad_containers(
    db_session: AsyncSession,
) -> None:
    route = respx.post(URL).respond(200, json={"ok": True})
    await _seed(db_session, active=300, broken=0, checked_ago_h=20)
    store = FakeStore()
    store.data["watchdog:restarts:radio-icy-worker-prod"] = "100"
    containers = _healthy_containers(
        **{
            "radio-icy-worker-prod": "radio-icy-worker-prod running healthy 150",
            "radio-redis-prod": "radio-redis-prod exited none 0",
        },
    )
    async with Alerter(SETTINGS, store=store, client=httpx.AsyncClient()) as a:
        await run_check(a, db_session, containers)
    texts = " | ".join(_sent_texts(route))
    assert "Health-check sin ejecutarse" in texts
    assert "radio-redis-prod" in texts
    assert "reiniciado 50 veces" in texts


@respx.mock
async def test_check_resolves_when_container_recovers(db_session: AsyncSession) -> None:
    route = respx.post(URL).respond(200, json={"ok": True})
    await _seed(db_session, active=300, broken=0, checked_ago_h=1)
    store = FakeStore()
    async with Alerter(SETTINGS, store=store, client=httpx.AsyncClient()) as a:
        await run_check(
            a, db_session, _healthy_containers(**{"radio-web-prod": "radio-web-prod exited none 0"})
        )
        await run_check(a, db_session, _healthy_containers())
    texts = _sent_texts(route)
    assert any(t.startswith("🚨") and "radio-web-prod" in t for t in texts)
    assert any(t.startswith("✅") and "radio-web-prod" in t for t in texts)


@respx.mock
async def test_summary_message(db_session: AsyncSession) -> None:
    route = respx.post(URL).respond(200, json={"ok": True})
    await _seed(db_session, active=3, broken=2, checked_ago_h=2)
    async with Alerter(SETTINGS, store=FakeStore(), client=httpx.AsyncClient()) as a:
        await run_summary(a, db_session)
    (msg,) = _sent_texts(route)
    assert "Activas: 3" in msg
    assert "rotas: 2" in msg


# --- CLI: notify / resolve (los usa infra/deploy/run-job.sh y classify-llm.sh) ------------------


class _FakeAlerter:
    calls: list[tuple[str, str, str]] = []  # noqa: RUF012

    async def __aenter__(self) -> _FakeAlerter:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def send(self, key: str, text: str) -> bool:
        self.calls.append(("send", key, text))
        return True

    async def resolve(self, key: str, text: str) -> bool:
        self.calls.append(("resolve", key, text))
        return True


def _invoke(monkeypatch: pytest.MonkeyPatch, *args: str) -> list[tuple[str, str, str]]:
    _FakeAlerter.calls = []
    monkeypatch.setattr(
        watchdog.Alerter, "from_env", classmethod(lambda _cls, **_kw: _FakeAlerter())
    )
    result = CliRunner().invoke(watchdog.app, list(args))
    assert result.exit_code == 0, result.output
    return list(_FakeAlerter.calls)


def test_cli_notify_sends_with_key_and_message(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _invoke(monkeypatch, "notify", "--key", "cron:x", "--message", "boom")
    assert calls == [("send", "cron:x", "boom")]


def test_cli_resolve_closes_the_alert_with_key_and_message(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _invoke(monkeypatch, "resolve", "--key", "cron:x", "--message", "ya funciona")
    assert calls == [("resolve", "cron:x", "ya funciona")]
