"""fetch-logos: selección, estados, backoff y concurrencia (ADR 011)."""

from __future__ import annotations

import asyncio
from io import BytesIO
from typing import TYPE_CHECKING

import httpx
import pytest
from PIL import Image
from sqlalchemy import text

from scripts import url_guard
from scripts.logo_cmd import (
    BACKOFF_DAYS,
    PER_HOST_CONCURRENCY,
    Candidate,
    backoff,
    process_candidates,
    select_candidates,
)
from scripts.url_guard import guard_request

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

PUBLIC = "93.184.216.34"


def _png(color: tuple[int, int, int, int] = (30, 140, 220, 255)) -> bytes:
    out = BytesIO()
    Image.new("RGBA", (160, 160), color).save(out, format="PNG")
    return out.getvalue()


@pytest.fixture(autouse=True)
def _public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALLOW_PRIVATE_STREAM_HOSTS", raising=False)

    async def fake(_host: str, _port: int) -> list[str]:
        return [PUBLIC]

    monkeypatch.setattr(url_guard, "_resolve", fake)


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
        event_hooks={"request": [guard_request]},
    )


async def _station(
    session: AsyncSession,
    slug: str,
    *,
    favicon: str | None = "https://cdn.example/logo.png",
    status: str = "active",
    hidden: bool = False,
    quality: int = 50,
) -> str:
    row = (
        await session.execute(
            text(
                """
                INSERT INTO stations (name, slug, status, hidden, quality_score, favicon_url, source)
                VALUES (:slug, :slug, CAST(:st AS station_status), :hidden, :q, :fav, 'radio-browser')
                RETURNING id
                """,
            ),
            {"slug": slug, "st": status, "hidden": hidden, "q": quality, "fav": favicon},
        )
    ).scalar_one()
    await session.commit()
    return str(row)


async def _logo_row(session: AsyncSession, station_id: str) -> dict[str, object] | None:
    session.expire_all()
    row = (
        (
            await session.execute(
                text(
                    """
                SELECT l.status, l.source_url, l.content_hash, l.attempts, l.last_error,
                       l.data_sm IS NOT NULL AS has_sm, l.data_lg IS NOT NULL AS has_lg,
                       l.next_retry_at > now() AS retry_in_future,
                       EXTRACT(EPOCH FROM (l.next_retry_at - now())) / 86400 AS retry_days,
                       s.logo_hash
                FROM stations s LEFT JOIN station_logos l ON l.station_id = s.id
                WHERE s.id = :id
                """,
                ),
                {"id": station_id},
            )
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


async def _run(
    maker: async_sessionmaker[AsyncSession],
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    dry_run: bool = False,
    slug: str | None = None,
) -> tuple[int, int, int]:
    async with maker() as session:
        candidates = await select_candidates(session, limit=100, slug=slug)
    async with _client(handler) as client:
        stats = await process_candidates(maker, client, candidates, dry_run=dry_run)
    return stats.ok, stats.failed, stats.rejected


def _ok(_r: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=_png(), headers={"content-type": "image/png"})


def _status(code: int) -> Callable[[httpx.Request], httpx.Response]:
    def handler(_r: httpx.Request) -> httpx.Response:
        return httpx.Response(code)

    return handler


async def _backdate(session: AsyncSession, station_id: str, sql_set: str) -> None:
    await session.execute(
        text(f"UPDATE station_logos SET {sql_set} WHERE station_id = :id"),  # noqa: S608
        {"id": station_id},
    )
    await session.commit()


# --- backoff ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("attempts", "days"),
    [(0, 1), (1, 1), (2, 3), (3, 7), (4, 14), (5, 30), (6, 30), (99, 30)],
)
def test_backoff_grows_and_caps_at_30_days(attempts: int, days: int) -> None:
    assert backoff(attempts).days == days
    assert days in BACKOFF_DAYS


# --- camino feliz ----------------------------------------------------------


async def test_new_logo_is_stored_and_the_station_gets_its_hash(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    sid = await _station(db_session, "radio-a")
    assert await _run(maker, _ok) == (1, 0, 0)

    row = await _logo_row(db_session, sid)
    assert row is not None
    assert row["status"] == "ok"
    assert row["has_sm"] is True
    assert row["has_lg"] is True
    assert row["attempts"] == 0
    assert row["logo_hash"] == row["content_hash"]
    assert len(str(row["logo_hash"])) == 12


async def test_a_second_run_has_nothing_to_do(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    await _station(db_session, "radio-a")
    assert await _run(maker, _ok) == (1, 0, 0)
    assert await _run(maker, _ok) == (0, 0, 0)  # idempotente


# --- quién entra en la cola -----------------------------------------------


async def test_only_active_visible_stations_with_a_favicon_are_candidates(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    await _station(db_session, "good")
    await _station(db_session, "no-favicon", favicon=None)
    await _station(db_session, "pending", status="pending")
    await _station(db_session, "broken", status="broken")
    await _station(db_session, "spam", hidden=True)
    async with maker() as session:
        got = {c.slug for c in await select_candidates(session, limit=100)}
    assert got == {"good"}


async def test_new_stations_go_first_and_best_quality_first(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    await _station(db_session, "low", quality=10)
    await _station(db_session, "high", quality=90)
    await _station(db_session, "done", quality=99)
    await _run(maker, _ok, slug="done")  # ya tiene fila en station_logos
    await _backdate(
        db_session,
        (await _logo_row_id(db_session, "done")),
        "fetched_at = now() - interval '40 days'",
    )
    async with maker() as session:
        order = [c.slug for c in await select_candidates(session, limit=100)]
    assert order == ["high", "low", "done"]


async def _logo_row_id(session: AsyncSession, slug: str) -> str:
    return str(
        (
            await session.execute(text("SELECT id FROM stations WHERE slug = :s"), {"s": slug})
        ).scalar_one()
    )


async def test_limit_is_respected(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    for i in range(5):
        await _station(db_session, f"s{i}")
    async with maker() as session:
        assert len(await select_candidates(session, limit=3)) == 3


async def test_a_changed_favicon_url_is_fetched_again(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    sid = await _station(db_session, "radio-a")
    await _run(maker, _ok)
    first = (await _logo_row(db_session, sid))["content_hash"]  # type: ignore[index]

    await db_session.execute(
        text("UPDATE stations SET favicon_url = 'https://cdn.example/new.png' WHERE id = :id"),
        {"id": sid},
    )
    await db_session.commit()

    def other(_r: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=_png((220, 30, 30, 255)), headers={"content-type": "image/png"}
        )

    assert await _run(maker, other) == (1, 0, 0)
    row = await _logo_row(db_session, sid)
    assert row is not None
    assert row["source_url"] == "https://cdn.example/new.png"
    assert row["content_hash"] != first


async def test_a_logo_is_refreshed_after_30_days_but_not_before(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    sid = await _station(db_session, "radio-a")
    await _run(maker, _ok)
    await _backdate(db_session, sid, "fetched_at = now() - interval '29 days'")
    assert await _run(maker, _ok) == (0, 0, 0)
    await _backdate(db_session, sid, "fetched_at = now() - interval '31 days'")
    assert await _run(maker, _ok) == (1, 0, 0)


# --- fallos y backoff -------------------------------------------------------


@pytest.mark.parametrize("code", [404, 403, 429, 500])
async def test_a_transient_failure_is_recorded_with_a_one_day_backoff(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession, code: int
) -> None:
    sid = await _station(db_session, "radio-a")
    assert await _run(maker, _status(code)) == (0, 1, 0)

    row = await _logo_row(db_session, sid)
    assert row is not None
    assert row["status"] == "failed"
    assert row["attempts"] == 1
    assert str(code) in str(row["last_error"])
    assert row["logo_hash"] is None
    assert row["retry_in_future"] is True
    assert 0.9 < float(row["retry_days"]) < 1.1  # type: ignore[arg-type]


async def test_a_failed_logo_is_not_retried_before_its_backoff_and_then_it_backs_off_more(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    sid = await _station(db_session, "radio-a")
    await _run(maker, _status(500))
    assert await _run(maker, _status(500)) == (0, 0, 0)  # aún no toca

    await _backdate(db_session, sid, "next_retry_at = now() - interval '1 minute'")
    assert await _run(maker, _status(500)) == (0, 1, 0)
    row = await _logo_row(db_session, sid)
    assert row is not None
    assert row["attempts"] == 2
    assert 2.9 < float(row["retry_days"]) < 3.1  # type: ignore[arg-type]


async def test_a_failed_logo_recovers_once_the_host_answers(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    sid = await _station(db_session, "radio-a")
    await _run(maker, _status(500))
    await _backdate(db_session, sid, "next_retry_at = now() - interval '1 minute'")
    assert await _run(maker, _ok) == (1, 0, 0)
    row = await _logo_row(db_session, sid)
    assert row is not None
    assert (row["status"], row["attempts"], row["last_error"]) == ("ok", 0, None)
    assert row["logo_hash"] is not None


async def test_a_failed_refresh_keeps_the_valid_logo_it_already_had(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    sid = await _station(db_session, "radio-a")
    await _run(maker, _ok)
    good = (await _logo_row(db_session, sid))["content_hash"]  # type: ignore[index]
    await _backdate(db_session, sid, "fetched_at = now() - interval '40 days'")

    assert await _run(maker, _status(503)) == (0, 1, 0)
    row = await _logo_row(db_session, sid)
    assert row is not None
    assert row["status"] == "ok"  # sigue sirviéndose
    assert row["content_hash"] == good
    assert row["logo_hash"] == good
    assert row["has_sm"] is True
    assert row["retry_in_future"] is True  # y no se reintenta cada noche
    assert await _run(maker, _status(503)) == (0, 0, 0)


async def test_when_the_url_changes_and_the_new_one_fails_the_old_logo_is_dropped(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    sid = await _station(db_session, "radio-a")
    await _run(maker, _ok)
    await db_session.execute(
        text("UPDATE stations SET favicon_url = 'https://other.example/x.png' WHERE id = :id"),
        {"id": sid},
    )
    await db_session.commit()

    assert await _run(maker, _status(500)) == (0, 1, 0)
    row = await _logo_row(db_session, sid)
    assert row is not None
    assert row["status"] == "failed"
    assert row["has_sm"] is False
    assert row["has_lg"] is False
    assert row["content_hash"] is None  # el hash viejo tampoco sobrevive
    assert row["logo_hash"] is None
    assert row["attempts"] == 1


# --- rechazos ---------------------------------------------------------------


@pytest.mark.parametrize(
    "content",
    [b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", b"garbage"],
)
async def test_an_unusable_image_is_rejected_for_good(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession, content: bytes
) -> None:
    sid = await _station(db_session, "radio-a")

    def handler(_r: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content, headers={"content-type": "image/png"})

    assert await _run(maker, handler) == (0, 0, 1)
    row = await _logo_row(db_session, sid)
    assert row is not None
    assert row["status"] == "rejected"
    assert row["logo_hash"] is None
    assert row["has_sm"] is False
    assert row["retry_in_future"] is None  # sin reintento programado
    assert await _run(maker, handler) == (0, 0, 0)  # y no vuelve a la cola


async def test_a_rejected_logo_is_tried_again_when_the_url_changes(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    sid = await _station(db_session, "radio-a")

    def svg(_r: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<svg/>", headers={"content-type": "image/svg+xml"})

    await _run(maker, svg)
    await db_session.execute(
        text("UPDATE stations SET favicon_url = 'https://cdn.example/real.png' WHERE id = :id"),
        {"id": sid},
    )
    await db_session.commit()
    assert await _run(maker, _ok) == (1, 0, 0)


async def test_an_internal_favicon_url_is_rejected_and_never_requested(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    sid = await _station(db_session, "evil", favicon="http://169.254.169.254/latest/meta-data/")
    calls = 0

    def handler(_r: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200)

    assert await _run(maker, handler) == (0, 0, 1)
    assert calls == 0
    row = await _logo_row(db_session, sid)
    assert row is not None
    assert row["status"] == "rejected"
    assert "blocked" in str(row["last_error"])


# --- varios ------------------------------------------------------------------


async def test_dry_run_downloads_but_writes_nothing(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    sid = await _station(db_session, "radio-a")
    assert await _run(maker, _ok, dry_run=True) == (1, 0, 0)
    row = await _logo_row(db_session, sid)
    assert row is not None
    assert row["status"] is None  # no hay fila en station_logos
    assert row["logo_hash"] is None


async def test_forcing_a_station_by_slug_ignores_the_deadlines(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    await _station(db_session, "radio-a")
    await _run(maker, _ok)
    assert await _run(maker, _ok) == (0, 0, 0)
    assert await _run(maker, _ok, slug="radio-a") == (1, 0, 0)


async def test_one_broken_logo_does_not_stop_the_others(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    await _station(db_session, "good", favicon="https://good.example/a.png")
    await _station(db_session, "bad", favicon="https://bad.example/a.png")

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.host == "bad.example":
            raise httpx.ConnectError("refused")
        return _ok(req)

    assert await _run(maker, handler) == (1, 1, 0)


async def test_no_more_than_two_simultaneous_downloads_per_host(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    for i in range(8):
        await _station(db_session, f"s{i}", favicon=f"https://i.ibb.co/{i}/logo.png")
    running = peak = 0

    async def handler(_r: httpx.Request) -> httpx.Response:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.05)
        running -= 1
        return _ok(_r)

    async with maker() as session:
        candidates = await select_candidates(session, limit=100)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), event_hooks={"request": [guard_request]}
    ) as client:
        stats = await process_candidates(maker, client, candidates, concurrency=8)
    assert stats.ok == 8
    assert peak == PER_HOST_CONCURRENCY


async def test_candidates_are_plain_data() -> None:
    c = Candidate(
        station_id=__import__("uuid").uuid4(),
        slug="x",
        url="u",
        previous_url=None,
        previous_attempts=0,
    )
    assert c.previous_url is None
