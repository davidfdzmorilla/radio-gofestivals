from __future__ import annotations

from typing import TYPE_CHECKING, Any

import respx
from sqlalchemy import text

from scripts.rb_client import RadioBrowserClient
from scripts.rb_sync import run_sync

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def _items_with_metadata() -> list[dict[str, Any]]:
    return [
        {
            "stationuuid": "10000000-0000-0000-0000-000000000001",
            "name": "Popular Techno",
            "url": "https://stream.example.com/pt.mp3",
            "url_resolved": "https://stream.example.com/pt.mp3",
            "countrycode": "es",
            "state": "Madrid",
            "codec": "MP3",
            "bitrate": 320,
            "language": "spanish",
            "tags": "techno",
            "clickcount": 5000,
            "votes": 250,
            "changeuuid": "abcdef00-0000-4000-8000-000000000001",
            "lastlocalchecktime": "2026-04-25 16:34:58",
        },
        {
            "stationuuid": "10000000-0000-0000-0000-000000000002",
            "name": "Empty Metadata",
            "url": "https://stream.example.com/em.mp3",
            "url_resolved": "https://stream.example.com/em.mp3",
            "countrycode": "de",
            "state": "Berlin",
            "codec": "aac",
            "bitrate": 128,
            "language": "german",
            "tags": "house",
            # clickcount, votes, changeuuid, lastlocalchecktime missing entirely
        },
    ]


@respx.mock
async def test_rb_sync_persists_radio_browser_metadata(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    respx.get(url__regex=r"https://host-a\.example/.*").respond(
        json=_items_with_metadata(),
    )
    client = RadioBrowserClient(servers=["host-a.example"])

    stats = await run_sync(
        maker, tag="techno", dry_run=False, limit=500, client=client,
    )
    assert stats.inserted == 2

    rows = (
        await db_session.execute(
            text(
                """
                SELECT name, clickcount, votes, last_changeuuid::text,
                       last_local_checktime, click_trend, quality_score
                FROM stations ORDER BY name
                """,
            ),
        )
    ).all()
    by_name = {r[0]: r for r in rows}

    popular = by_name["Popular Techno"]
    assert popular[1] == 5000  # clickcount
    assert popular[2] == 250  # votes
    assert popular[3] == "abcdef00-0000-4000-8000-000000000001"
    assert popular[4] is not None  # last_local_checktime
    assert popular[5] == 0  # click_trend default
    # bitrate=320 + opus-tier algorithm + heavy popularity → high quality
    assert popular[6] >= 80

    empty = by_name["Empty Metadata"]
    assert empty[1] == 0  # default
    assert empty[2] == 0
    assert empty[3] is None
    assert empty[4] is None
    assert empty[5] == 0
