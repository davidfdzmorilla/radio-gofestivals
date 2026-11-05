"""favicon_url: rb_sync guarda la URL del logo de Radio-Browser (ADR 011).

Solo la URL de origen: la descarga y el procesado los hace `fetch-logos`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
import respx
from sqlalchemy import text

from scripts.rb_client import RadioBrowserClient
from scripts.rb_sync import MAX_FAVICON_LENGTH, parse_favicon_url, run_sync

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def _item(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "stationuuid": "00000000-0000-0000-0000-0000000000bb",
        "name": "Favicon FM",
        "url": "https://stream.example.com/fav.mp3",
        "url_resolved": "https://stream.example.com/fav.mp3",
        "countrycode": "es",
        "codec": "mp3",
        "bitrate": 128,
        "language": "spanish",
        "tags": "techno",
        "homepage": "https://favicon.fm/",
        "favicon": "https://favicon.fm/logo.png",
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://i.ibb.co/T1gH75m/logo.png", "https://i.ibb.co/T1gH75m/logo.png"),
        ("  http://radio.example/logo.jpg  ", "http://radio.example/logo.jpg"),
        ("HTTPS://RADIO.EXAMPLE/LOGO.PNG", "HTTPS://RADIO.EXAMPLE/LOGO.PNG"),
    ],
)
def test_parse_favicon_url_accepts_http_and_https(raw: str, expected: str) -> None:
    assert parse_favicon_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "   ",
        "javascript:alert(1)",
        "data:image/png;base64,AAAA",
        "file:///etc/passwd",
        "ftp://radio.example/logo.png",
        "//radio.example/logo.png",
        "/logo.png",
        "radio.example/logo.png",
        "https://radio.example/a b.png",
        "https://radio.example/a\nb.png",
        "https://radio.example/a\x00b.png",
        "https://radio.example/" + "a" * MAX_FAVICON_LENGTH,
    ],
)
def test_parse_favicon_url_rejects_unusable_values(raw: object) -> None:
    assert parse_favicon_url(raw) is None


@respx.mock
async def test_sync_persists_favicon(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    respx.get(url__regex=r"https://host-a\.example/.*").respond(json=[_item()])
    client = RadioBrowserClient(servers=["host-a.example"])
    await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)

    row = (
        await db_session.execute(
            text("SELECT favicon_url, logo_hash FROM stations WHERE name = 'Favicon FM'"),
        )
    ).first()
    assert row is not None
    assert row[0] == "https://favicon.fm/logo.png"
    assert row[1] is None  # el hash solo lo pone fetch-logos


@respx.mock
async def test_sync_refreshes_favicon_but_never_nulls_it(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    async def favicon() -> str | None:
        row = (
            await db_session.execute(
                text("SELECT favicon_url FROM stations WHERE name = 'Favicon FM'"),
            )
        ).first()
        assert row is not None
        db_session.expire_all()
        return row[0]

    respx.get(url__regex=r"https://host-a\.example/.*").respond(json=[_item()])
    await run_sync(
        maker,
        tag="techno",
        dry_run=False,
        limit=500,
        client=RadioBrowserClient(servers=["host-a.example"]),
    )
    assert await favicon() == "https://favicon.fm/logo.png"

    respx.clear()
    respx.get(url__regex=r"https://host-b\.example/.*").respond(
        json=[_item(favicon="https://favicon.fm/new.webp")],
    )
    await run_sync(
        maker,
        tag="techno",
        dry_run=False,
        limit=500,
        client=RadioBrowserClient(servers=["host-b.example"]),
    )
    assert await favicon() == "https://favicon.fm/new.webp"

    # RB deja de traer favicon (o trae basura): se conserva el último válido.
    for bad in ("", "javascript:alert(1)"):
        respx.clear()
        respx.get(url__regex=r"https://host-c\.example/.*").respond(json=[_item(favicon=bad)])
        await run_sync(
            maker,
            tag="techno",
            dry_run=False,
            limit=500,
            client=RadioBrowserClient(servers=["host-c.example"]),
        )
        assert await favicon() == "https://favicon.fm/new.webp"
