"""homepage_url: rb_sync debe poblarla (alimenta el sameAs del JSON-LD,
el outreach de /for-stations y afina el dedupe por marca)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import respx
from sqlalchemy import text

from scripts.rb_client import RadioBrowserClient
from scripts.rb_sync import run_sync

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def _item(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "stationuuid": "00000000-0000-0000-0000-0000000000aa",
        "name": "Homepage FM",
        "url": "https://stream.example.com/hp.mp3",
        "url_resolved": "https://stream.example.com/hp.mp3",
        "countrycode": "es",
        "codec": "mp3",
        "bitrate": 128,
        "language": "spanish",
        "tags": "techno",
        "homepage": "https://homepage.fm/",
    }
    base.update(overrides)
    return base


@respx.mock
async def test_sync_persists_homepage(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    respx.get(url__regex=r"https://host-a\.example/.*").respond(json=[_item()])
    client = RadioBrowserClient(servers=["host-a.example"])
    await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)

    row = (
        await db_session.execute(
            text("SELECT homepage_url FROM stations WHERE name = 'Homepage FM'"),
        )
    ).first()
    assert row is not None
    assert row[0] == "https://homepage.fm/"


@respx.mock
async def test_sync_refreshes_homepage_but_never_nulls_it(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    respx.get(url__regex=r"https://host-a\.example/.*").respond(json=[_item()])
    client = RadioBrowserClient(servers=["host-a.example"])
    await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)

    # Segundo run: RB trae otra homepage → se actualiza.
    respx.clear()
    respx.get(url__regex=r"https://host-b\.example/.*").respond(
        json=[_item(homepage="https://nueva.homepage.fm/")],
    )
    client = RadioBrowserClient(servers=["host-b.example"])
    await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)
    row = (
        await db_session.execute(
            text("SELECT homepage_url FROM stations WHERE name = 'Homepage FM'"),
        )
    ).first()
    assert row is not None
    assert row[0] == "https://nueva.homepage.fm/"

    # Tercer run: RB ya no trae homepage → se conserva (no se pisa a NULL).
    respx.clear()
    respx.get(url__regex=r"https://host-c\.example/.*").respond(
        json=[_item(homepage="")],
    )
    client = RadioBrowserClient(servers=["host-c.example"])
    await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)
    row = (
        await db_session.execute(
            text("SELECT homepage_url FROM stations WHERE name = 'Homepage FM'"),
        )
    ).first()
    assert row is not None
    assert row[0] == "https://nueva.homepage.fm/"


@respx.mock
async def test_sync_rejects_non_http_homepage(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    respx.get(url__regex=r"https://host-a\.example/.*").respond(
        json=[_item(homepage="javascript:alert(1)")],
    )
    client = RadioBrowserClient(servers=["host-a.example"])
    await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)

    row = (
        await db_session.execute(
            text("SELECT homepage_url FROM stations WHERE name = 'Homepage FM'"),
        )
    ).first()
    assert row is not None
    assert row[0] is None


@respx.mock
async def test_brand_attach_respects_homepage_mismatch(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    """Misma marca (nombre+país): homepage vacía es comodín (attach);
    homepage distinta es otra emisora (insert)."""
    respx.get(url__regex=r"https://host-a\.example/.*").respond(json=[_item()])
    client = RadioBrowserClient(servers=["host-a.example"])
    await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)

    # Mismo nombre+país, rb_uuid distinto, MISMA homepage → attach (1 station).
    respx.clear()
    respx.get(url__regex=r"https://host-b\.example/.*").respond(
        json=[
            _item(
                stationuuid="00000000-0000-0000-0000-0000000000bb",
                url="https://stream.example.com/hp-320.mp3",
                url_resolved="https://stream.example.com/hp-320.mp3",
                bitrate=320,
            ),
        ],
    )
    client = RadioBrowserClient(servers=["host-b.example"])
    await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)
    count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM stations WHERE name = 'Homepage FM'"),
        )
    ).scalar_one()
    assert count == 1

    # Mismo nombre+país, homepage DIFERENTE → emisora nueva (2 stations).
    respx.clear()
    respx.get(url__regex=r"https://host-c\.example/.*").respond(
        json=[
            _item(
                stationuuid="00000000-0000-0000-0000-0000000000cc",
                url="https://stream.example.com/other.mp3",
                url_resolved="https://stream.example.com/other.mp3",
                homepage="https://otra-emisora.example/",
            ),
        ],
    )
    client = RadioBrowserClient(servers=["host-c.example"])
    await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)
    count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM stations WHERE name = 'Homepage FM'"),
        )
    ).scalar_one()
    assert count == 2
