"""fetch-logos: selección, estados, backoff y concurrencia (ADR 011)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from io import BytesIO
from typing import TYPE_CHECKING

import httpx
import pytest
from PIL import Image
from sqlalchemy import text

from scripts import url_guard
from scripts.logo_cmd import (
    BACKOFF_DAYS,
    GENERIC_ICON_MIN_SITES,
    PER_HOST_CONCURRENCY,
    Candidate,
    backoff,
    find_unwanted_homepage_logos,
    process_candidates,
    purge_unwanted_logos,
    select_candidates,
)
from scripts.url_guard import guard_request

if TYPE_CHECKING:
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
    homepage: str | None = None,
    status: str = "active",
    hidden: bool = False,
    quality: int = 50,
) -> str:
    row = (
        await session.execute(
            text(
                """
                INSERT INTO stations
                    (name, slug, status, hidden, quality_score, favicon_url, homepage_url, source)
                VALUES (:slug, :slug, CAST(:st AS station_status), :hidden, :q, :fav, :home,
                        'radio-browser')
                RETURNING id
                """,
            ),
            {
                "slug": slug,
                "st": status,
                "hidden": hidden,
                "q": quality,
                "fav": favicon,
                "home": homepage,
            },
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
                SELECT l.status, l.source_url, l.source_kind, l.favicon_seen, l.homepage_seen,
                       l.content_hash, l.attempts, l.last_error,
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
        favicon_url=None,
        homepage_url="https://x.example",
        previous_attempts=0,
        inputs_unchanged=False,
        keep_previous=False,
    )
    assert c.source_url == "https://x.example"


# --- escalera: favicon -> icono de la web (ADR 011, addendum) ---------------

Route = Callable[[], httpx.Response]


def _page(*links: str, status: int = 200) -> httpx.Response:
    body = "<html><head>" + "".join(links) + "</head><body></body></html>"
    return httpx.Response(status, content=body.encode(), headers={"content-type": "text/html"})


def _img(color: tuple[int, int, int, int] = (30, 140, 220, 255)) -> httpx.Response:
    return httpx.Response(200, content=_png(color), headers={"content-type": "image/png"})


def _site(
    routes: dict[tuple[str, str], Route],
) -> tuple[Callable[[httpx.Request], httpx.Response], list[tuple[str, str]]]:
    """Handler por (host, ruta) que anota cada petición; lo no declarado es un 404."""
    seen: list[tuple[str, str]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        key = (req.url.host, req.url.path)
        seen.append(key)
        route = routes.get(key)
        return route() if route else httpx.Response(404)

    return handler, seen


ATI = '<link rel="apple-touch-icon" href="/ati.png" sizes="180x180">'


async def test_a_good_favicon_never_touches_the_homepage(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    sid = await _station(
        db_session,
        "radio-a",
        favicon="https://cdn.example/f.png",
        homepage="https://radio.example/",
    )
    handler, seen = _site(
        {("cdn.example", "/f.png"): _img, ("radio.example", "/"): lambda: _page(ATI)}
    )
    assert await _run(maker, handler) == (1, 0, 0)
    assert seen == [("cdn.example", "/f.png")]
    row = await _logo_row(db_session, sid)
    assert row is not None
    assert row["source_kind"] == "favicon"
    assert row["source_url"] == "https://cdn.example/f.png"
    assert row["favicon_seen"] == "https://cdn.example/f.png"
    assert row["homepage_seen"] == "https://radio.example/"


async def test_a_dead_favicon_falls_back_to_the_homepage_icon(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    sid = await _station(
        db_session,
        "radio-a",
        favicon="https://cdn.example/dead.png",
        homepage="https://radio.example/",
    )
    handler, seen = _site(
        {("radio.example", "/"): lambda: _page(ATI), ("radio.example", "/ati.png"): _img}
    )
    assert await _run(maker, handler) == (1, 0, 0)
    assert seen == [
        ("cdn.example", "/dead.png"),
        ("radio.example", "/"),
        ("radio.example", "/ati.png"),
    ]
    row = await _logo_row(db_session, sid)
    assert row is not None
    assert (row["status"], row["source_kind"]) == ("ok", "homepage")
    assert row["source_url"] == "https://radio.example/ati.png"
    assert row["logo_hash"] == row["content_hash"]
    assert row["attempts"] == 0


async def test_a_station_without_favicon_uses_its_homepage(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    sid = await _station(db_session, "radio-a", favicon=None, homepage="https://radio.example/")
    handler, _ = _site(
        {("radio.example", "/"): lambda: _page(ATI), ("radio.example", "/ati.png"): _img}
    )
    assert await _run(maker, handler) == (1, 0, 0)
    row = await _logo_row(db_session, sid)
    assert row is not None
    assert (row["status"], row["source_kind"], row["favicon_seen"]) == ("ok", "homepage", None)


async def test_a_too_small_favicon_also_falls_back_to_the_homepage(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    sid = await _station(
        db_session,
        "radio-a",
        favicon="https://cdn.example/tiny.png",
        homepage="https://radio.example/",
    )

    def tiny() -> httpx.Response:
        out = BytesIO()
        Image.new("RGBA", (16, 16), (30, 140, 220, 255)).save(out, format="PNG")
        return httpx.Response(200, content=out.getvalue(), headers={"content-type": "image/png"})

    handler, _ = _site(
        {
            ("cdn.example", "/tiny.png"): tiny,
            ("radio.example", "/"): lambda: _page(ATI),
            ("radio.example", "/ati.png"): _img,
        }
    )
    assert await _run(maker, handler) == (1, 0, 0)
    assert (await _logo_row(db_session, sid))["source_kind"] == "homepage"  # type: ignore[index]


async def test_the_next_icon_candidate_is_tried_when_the_first_one_fails(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    sid = await _station(db_session, "radio-a", favicon=None, homepage="https://radio.example/")
    page = _page(
        '<link rel="apple-touch-icon" href="/missing.png" sizes="180x180">',
        '<link rel="apple-touch-icon" href="/ok.png" sizes="152x152">',
    )
    handler, seen = _site(
        {("radio.example", "/"): lambda: page, ("radio.example", "/ok.png"): _img}
    )
    assert await _run(maker, handler) == (1, 0, 0)
    assert ("radio.example", "/missing.png") in seen
    assert (await _logo_row(db_session, sid))["source_url"] == "https://radio.example/ok.png"  # type: ignore[index]


async def test_an_invisible_icon_is_skipped_for_the_next_one(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    sid = await _station(db_session, "radio-a", favicon=None, homepage="https://radio.example/")

    def white() -> httpx.Response:
        out = BytesIO()
        Image.new("RGBA", (180, 180), (255, 255, 255, 255)).save(out, format="PNG")
        return httpx.Response(200, content=out.getvalue(), headers={"content-type": "image/png"})

    page = _page(
        '<link rel="apple-touch-icon" href="/white.png" sizes="180x180">',
        '<link rel="icon" href="/real.png" sizes="128x128">',
    )
    handler, _ = _site(
        {
            ("radio.example", "/"): lambda: page,
            ("radio.example", "/white.png"): white,
            ("radio.example", "/real.png"): _img,
        }
    )
    assert await _run(maker, handler) == (1, 0, 0)
    assert (await _logo_row(db_session, sid))["source_url"] == "https://radio.example/real.png"  # type: ignore[index]


@pytest.mark.parametrize(
    "home",
    [
        "https://www.facebook.com/miradio",
        "https://miradio.wixsite.com/x",
        "https://laut.fm/miradio",
        "https://x.com/miradio",
    ],
)
async def test_social_and_platform_homepages_are_never_requested(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession, home: str
) -> None:
    sid = await _station(db_session, "radio-a", favicon=None, homepage=home)
    handler, seen = _site({})
    assert await _run(maker, handler) == (0, 0, 1)
    assert seen == []
    row = await _logo_row(db_session, sid)
    assert row is not None
    assert row["status"] == "rejected"
    assert "social network or generic platform" in str(row["last_error"])
    assert row["homepage_seen"] == home
    assert await _run(maker, handler) == (0, 0, 0)  # y no vuelve a la cola


async def test_a_homepage_without_a_usable_icon_is_retried_later_not_forever_rejected(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    sid = await _station(db_session, "radio-a", favicon=None, homepage="https://radio.example/")
    handler, _ = _site({("radio.example", "/"): lambda: _page("<title>sin iconos</title>")})
    assert await _run(maker, handler) == (0, 1, 0)
    row = await _logo_row(db_session, sid)
    assert row is not None
    assert (row["status"], row["attempts"]) == ("failed", 1)
    assert row["retry_in_future"] is True
    assert await _run(maker, handler) == (0, 0, 0)  # aún no toca

    await _backdate(db_session, sid, "next_retry_at = now() - interval '1 minute'")
    assert await _run(maker, handler) == (0, 1, 0)
    row = await _logo_row(db_session, sid)
    assert row is not None
    assert row["attempts"] == 2
    assert 2.9 < float(row["retry_days"]) < 3.1  # type: ignore[arg-type]


@pytest.mark.parametrize("status", [403, 404, 429, 503])
async def test_a_homepage_that_refuses_us_is_a_retryable_failure_and_is_respected(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession, status: int
) -> None:
    sid = await _station(db_session, "radio-a", favicon=None, homepage="https://radio.example/")
    handler, seen = _site({("radio.example", "/"): lambda: httpx.Response(status)})
    assert await _run(maker, handler) == (0, 1, 0)
    assert seen == [("radio.example", "/")]  # no se insiste ni se prueba nada más
    row = await _logo_row(db_session, sid)
    assert row is not None
    assert row["status"] == "failed"
    assert str(status) in str(row["last_error"])


async def test_a_homepage_that_redirects_to_an_internal_address_is_rejected_for_good(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake(host: str, _port: int) -> list[str]:
        return ["10.0.0.9"] if host == "internal.example" else [PUBLIC]

    monkeypatch.setattr(url_guard, "_resolve", fake)
    sid = await _station(db_session, "radio-a", favicon=None, homepage="https://radio.example/")
    seen: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.url.host)
        return httpx.Response(302, headers={"location": "http://internal.example/x"})

    assert await _run(maker, handler) == (0, 0, 1)
    assert seen == ["radio.example"]
    row = await _logo_row(db_session, sid)
    assert row is not None
    assert (row["status"], row["retry_in_future"]) == ("rejected", None)


async def test_an_icon_url_that_points_inside_is_never_requested(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    await _station(db_session, "radio-a", favicon=None, homepage="https://radio.example/")
    page = _page(
        '<link rel="apple-touch-icon" href="http://169.254.169.254/latest/meta-data/" sizes="180x180">'
    )
    handler, seen = _site({("radio.example", "/"): lambda: page})
    assert await _run(maker, handler) == (0, 1, 0)
    assert all(host != "169.254.169.254" for host, _ in seen)


# --- migración 0022: filas antiguas entran en la escalera --------------------


async def _legacy_row(
    session: AsyncSession,
    sid: str,
    *,
    status: str,
    with_homepage_seen: bool,
    favicon: str | None,
) -> None:
    """Fila como las que dejó la migración 0022: favicon_seen = source_url, origen favicon."""
    is_ok = status == "ok"
    await session.execute(
        text(
            """
            INSERT INTO station_logos
                (station_id, source_url, source_kind, favicon_seen, homepage_seen, status,
                 attempts, last_error, next_retry_at, content_hash, data_sm, data_lg)
            VALUES (:id, :fav, 'favicon', :fav, :home, :st, 1, 'too small', :retry,
                    :hash, :sm, :lg)
            """,
        ),
        {
            "id": sid,
            "fav": favicon,
            "home": "https://radio.example/" if with_homepage_seen else None,
            "st": status,
            "retry": datetime(2099, 1, 1) if status == "failed" else None,  # noqa: DTZ001
            "hash": "abcdef123456" if is_ok else None,
            "sm": b"\x01" if is_ok else None,
            "lg": b"\x02" if is_ok else None,
        },
    )
    await session.commit()


@pytest.mark.parametrize("status", ["rejected", "failed"])
async def test_rows_from_before_the_homepage_fallback_get_the_new_ladder(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession, status: str
) -> None:
    sid = await _station(
        db_session,
        "radio-a",
        favicon="https://cdn.example/f.png",
        homepage="https://radio.example/",
    )
    await _legacy_row(
        db_session,
        sid,
        status=status,
        with_homepage_seen=False,
        favicon="https://cdn.example/f.png",
    )
    handler, _ = _site(
        {("radio.example", "/"): lambda: _page(ATI), ("radio.example", "/ati.png"): _img}
    )
    # `failed` con el reintento programado en 2099 y `rejected` sin reintento: aun así entran,
    # porque la web nunca se había probado.
    assert await _run(maker, handler) == (1, 0, 0)
    assert (await _logo_row(db_session, sid))["source_kind"] == "homepage"  # type: ignore[index]


async def test_existing_good_logos_are_left_alone_by_the_migration(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    sid = await _station(
        db_session,
        "radio-a",
        favicon="https://cdn.example/f.png",
        homepage="https://radio.example/",
    )
    await _legacy_row(
        db_session, sid, status="ok", with_homepage_seen=True, favicon="https://cdn.example/f.png"
    )
    handler, seen = _site({})
    assert await _run(maker, handler) == (0, 0, 0)
    assert seen == []


async def test_a_good_logo_does_not_depend_on_the_homepage_changing(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    sid = await _station(
        db_session,
        "radio-a",
        favicon="https://cdn.example/f.png",
        homepage="https://radio.example/",
    )
    await _run(maker, _ok)
    await db_session.execute(
        text("UPDATE stations SET homepage_url = 'https://nueva.example/' WHERE id = :id"),
        {"id": sid},
    )
    await db_session.commit()
    assert await _run(maker, _ok) == (0, 0, 0)  # ya tiene logo: la web nueva no le afecta


async def test_a_logo_less_station_is_retried_when_its_homepage_changes(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    sid = await _station(db_session, "radio-a", favicon=None, homepage="https://old.example/")
    handler, _ = _site({("old.example", "/"): lambda: _page("<title>nada</title>")})
    assert await _run(maker, handler) == (0, 1, 0)
    await db_session.execute(
        text("UPDATE stations SET homepage_url = 'https://new.example/' WHERE id = :id"),
        {"id": sid},
    )
    await db_session.commit()
    handler2, _ = _site(
        {("new.example", "/"): lambda: _page(ATI), ("new.example", "/ati.png"): _img}
    )
    assert await _run(maker, handler2) == (1, 0, 0)  # sin esperar al backoff


async def test_a_failed_refresh_keeps_a_logo_that_came_from_the_homepage(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    sid = await _station(db_session, "radio-a", favicon=None, homepage="https://radio.example/")
    ok, _ = _site({("radio.example", "/"): lambda: _page(ATI), ("radio.example", "/ati.png"): _img})
    await _run(maker, ok)
    good = (await _logo_row(db_session, sid))["content_hash"]  # type: ignore[index]
    await _backdate(db_session, sid, "fetched_at = now() - interval '40 days'")

    down, _ = _site({("radio.example", "/"): lambda: httpx.Response(503)})
    assert await _run(maker, down) == (0, 1, 0)
    row = await _logo_row(db_session, sid)
    assert row is not None
    assert (row["status"], row["source_kind"], row["content_hash"], row["logo_hash"]) == (
        "ok",
        "homepage",
        good,
        good,
    )
    assert row["source_url"] == "https://radio.example/ati.png"


async def test_stations_with_only_a_homepage_are_candidates_and_with_neither_are_not(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    await _station(db_session, "only-home", favicon=None, homepage="https://radio.example/")
    await _station(db_session, "only-favicon")
    await _station(db_session, "neither", favicon=None, homepage=None)
    async with maker() as session:
        assert {c.slug for c in await select_candidates(session, limit=100)} == {
            "only-home",
            "only-favicon",
        }


async def test_the_per_host_limit_counts_homepage_and_icon_requests_too(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    for i in range(8):
        await _station(db_session, f"s{i}", favicon=None, homepage=f"https://brand.example/{i}")
    running = peak = 0

    async def handler(req: httpx.Request) -> httpx.Response:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.03)
        running -= 1
        return _page(ATI) if req.url.path != "/ati.png" else _img()

    async with maker() as session:
        candidates = await select_candidates(session, limit=100)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
        event_hooks={"request": [guard_request]},
    ) as client:
        stats = await process_candidates(maker, client, candidates, concurrency=8)
    assert stats.ok == 8
    assert stats.via_homepage == 8
    assert peak == PER_HOST_CONCURRENCY


async def test_dry_run_of_the_ladder_writes_nothing(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    sid = await _station(db_session, "radio-a", favicon=None, homepage="https://radio.example/")
    handler, _ = _site(
        {("radio.example", "/"): lambda: _page(ATI), ("radio.example", "/ati.png"): _img}
    )
    assert await _run(maker, handler, dry_run=True) == (1, 0, 0)
    row = await _logo_row(db_session, sid)
    assert row is not None
    assert row["status"] is None


# --- depuración: iconos genéricos y dominios denegados --------------------------


async def _ok_logo(
    session: AsyncSession,
    slug: str,
    *,
    homepage: str,
    content_hash: str,
    kind: str = "homepage",
    favicon: str | None = None,
) -> str:
    sid = await _station(session, slug, favicon=favicon, homepage=homepage)
    await session.execute(
        text(
            """
            INSERT INTO station_logos
                (station_id, source_url, source_kind, favicon_seen, homepage_seen, status,
                 content_hash, data_sm, data_lg)
            VALUES (:id, 'https://x.example/i.png', :kind, :fav, :home, 'ok', :hash, :sm, :lg)
            """,
        ),
        {
            "id": sid,
            "kind": kind,
            "fav": favicon,
            "home": homepage,
            "hash": content_hash,
            "sm": b"\x01",
            "lg": b"\x02",
        },
    )
    await session.execute(
        text("UPDATE stations SET logo_hash = :h WHERE id = :id"), {"h": content_hash, "id": sid}
    )
    await session.commit()
    return sid


async def test_one_image_on_three_unrelated_sites_is_a_generic_icon_and_is_purged(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    ids = [
        await _ok_logo(
            db_session, f"s{i}", homepage=f"https://{host}/x", content_hash="generic000000"
        )
        for i, host in enumerate(["r.bgp.rodeo", "a6.asurahosting.com", "pc.costa-server.info.pl"])
    ]
    assert GENERIC_ICON_MIN_SITES == 3
    assert await purge_unwanted_logos(maker) == 3
    for sid in ids:
        row = await _logo_row(db_session, sid)
        assert row is not None
        assert (
            row["status"],
            row["source_kind"],
            row["logo_hash"],
            row["has_sm"],
            row["has_lg"],
        ) == ("rejected", None, None, False, False)
        assert "generic icon shared by 3 different sites" in str(row["last_error"])
        assert row["retry_in_future"] is None


async def test_a_brand_with_many_channels_on_one_site_keeps_its_logo(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    ids = [
        await _ok_logo(
            db_session,
            f"rr{i}",
            homepage=f"https://radiorecord.ru/radio/ch{i}",
            content_hash="brand0000000",
        )
        for i in range(23)
    ]
    ids += [
        await _ok_logo(
            db_session,
            "rr-sub",
            homepage="https://www.radiorecord.ru/",
            content_hash="brand0000000",
        )
    ]
    assert await purge_unwanted_logos(maker) == 0
    assert (await _logo_row(db_session, ids[0]))["status"] == "ok"  # type: ignore[index]


async def test_two_sites_sharing_an_image_is_not_enough_to_call_it_generic(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    for i, host in enumerate(["brand-a.example", "brand-b.example"]):
        await _ok_logo(
            db_session, f"s{i}", homepage=f"https://{host}/", content_hash="pair00000000"
        )
    assert await purge_unwanted_logos(maker) == 0


async def test_the_threshold_counts_registrable_domains_not_hosts(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    for i, host in enumerate(["a.brand.fm", "b.brand.fm", "c.brand.fm", "www.brand.fm"]):
        await _ok_logo(
            db_session, f"s{i}", homepage=f"https://{host}/", content_hash="sub000000000"
        )
    assert await purge_unwanted_logos(maker) == 0  # 4 hosts, pero un solo sitio


async def test_a_logo_from_a_domain_added_to_the_denylist_later_is_purged(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    sid = await _ok_logo(
        db_session, "wix", homepage="https://usuario.wixsite.com/radio", content_hash="wix000000000"
    )
    assert await purge_unwanted_logos(maker) == 1
    row = await _logo_row(db_session, sid)
    assert row is not None
    assert (row["status"], row["logo_hash"]) == ("rejected", None)
    assert "denied domain" in str(row["last_error"])


async def test_favicon_logos_are_never_purged_even_if_shared(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    for i, host in enumerate(["a.example", "b.example", "c.example", "d.example"]):
        await _ok_logo(
            db_session,
            f"f{i}",
            homepage=f"https://{host}/",
            content_hash="fav000000000",
            kind="favicon",
            favicon=f"https://cdn{i}.example/f.png",
        )
    assert await purge_unwanted_logos(maker) == 0


async def test_purged_stations_do_not_come_back_to_the_queue_until_their_urls_change(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    for i, host in enumerate(["a.example", "b.example", "c.example"]):
        await _ok_logo(
            db_session, f"s{i}", homepage=f"https://{host}/", content_hash="generic000000"
        )
    await purge_unwanted_logos(maker)
    async with maker() as session:
        assert await select_candidates(session, limit=100) == []


async def test_purge_is_idempotent_and_ignores_stations_that_failed_or_were_rejected(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    for i, host in enumerate(["a.example", "b.example", "c.example"]):
        await _ok_logo(
            db_session, f"s{i}", homepage=f"https://{host}/", content_hash="generic000000"
        )
    assert await purge_unwanted_logos(maker) == 3
    assert await purge_unwanted_logos(maker) == 0


async def test_dry_run_reports_but_does_not_purge(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    ids = [
        await _ok_logo(db_session, f"s{i}", homepage=f"https://{h}/", content_hash="generic000000")
        for i, h in enumerate(["a.example", "b.example", "c.example"])
    ]
    assert await purge_unwanted_logos(maker, dry_run=True) == 3
    assert (await _logo_row(db_session, ids[0]))["status"] == "ok"  # type: ignore[index]
    async with maker() as session:
        assert len(await find_unwanted_homepage_logos(session)) == 3


async def test_a_fresh_generic_icon_found_by_the_ladder_is_purged_in_the_same_run(
    maker: async_sessionmaker[AsyncSession], db_session: AsyncSession
) -> None:
    """Fin a fin: tres webs sin relación sirven el mismo icono por defecto."""
    for i, host in enumerate(["a.example", "b.example", "c.example"]):
        await _station(db_session, f"s{i}", favicon=None, homepage=f"https://{host}/")

    def handler(req: httpx.Request) -> httpx.Response:
        return _page(ATI) if req.url.path == "/" else _img((30, 140, 220, 255))

    assert await _run(maker, handler) == (3, 0, 0)
    assert await purge_unwanted_logos(maker) == 3
