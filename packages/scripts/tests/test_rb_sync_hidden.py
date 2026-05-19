from __future__ import annotations

from typing import TYPE_CHECKING, Any

import respx
from sqlalchemy import text

from scripts.rb_client import RadioBrowserClient
from scripts.rb_sync import is_likely_spam, run_sync

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def _rb_item(
    *,
    stationuuid: str,
    name: str,
    url: str = "https://stream.example.com/x.mp3",
    tags: str = "techno",
) -> dict[str, Any]:
    return {
        "stationuuid": stationuuid,
        "name": name,
        "url": url,
        "url_resolved": url,
        "countrycode": "de",
        "state": "Berlin",
        "codec": "mp3",
        "bitrate": 192,
        "language": "german",
        "tags": tags,
    }


def test_is_likely_spam_canonical_cases() -> None:
    # Strong positive signals — must flag.
    assert is_likely_spam("# TOP 100 CLUB CHARTS @ TikTok Hits", None)
    assert is_likely_spam(
        "regular name",
        "https://breakz-high.rautemusik.fm/?ref=radiobrowser-top100",
    )
    assert is_likely_spam("__CLUB__ by rautemusik", None) is True
    assert is_likely_spam(">> MIX RADIO <<", None) is True
    assert is_likely_spam("A" * 81, None) is True

    # Negatives — must not flag.
    assert is_likely_spam("Techno Tribe", None) is False
    assert is_likely_spam("SomaFM Synphaera Radio", "https://somafm.com/synphaera") is False
    # CHARTS alone is not enough; needs the @ combo.
    assert is_likely_spam("Music Charts FM", None) is False


@respx.mock
async def test_new_spammy_station_inserted_as_hidden(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    items = [
        _rb_item(
            stationuuid="00000000-0000-0000-0000-0000000000aa",
            name="# TOP 100 CLUB CHARTS @ TikTok Hits, Ibiza House",
            url="https://breakz-high.rautemusik.fm/?ref=radiobrowser-top100-clubcharts",
        ),
        _rb_item(
            stationuuid="00000000-0000-0000-0000-0000000000bb",
            name="Techno Tribe",
            url="https://stream.example.com/tt.mp3",
        ),
    ]
    respx.get(url__regex=r"https://host-a\.example/.*").respond(json=items)
    client = RadioBrowserClient(servers=["host-a.example"])

    stats = await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)
    assert stats.inserted == 2

    rows = (
        await db_session.execute(
            text("SELECT name, hidden FROM stations ORDER BY name"),
        )
    ).all()
    by_name = {str(r[0]): bool(r[1]) for r in rows}
    assert by_name["# TOP 100 CLUB CHARTS @ TikTok Hits, Ibiza House"] is True
    assert by_name["Techno Tribe"] is False


@respx.mock
async def test_existing_hidden_false_not_overridden_on_resync(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    # First sync with a clean name → row lands with hidden=false.
    first = [
        _rb_item(
            stationuuid="00000000-0000-0000-0000-0000000000cc",
            name="Clean Name Radio",
        ),
    ]
    respx.get(url__regex=r"https://host-a\.example/.*").respond(json=first)
    client = RadioBrowserClient(servers=["host-a.example"])
    await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)

    # Confirm starting state.
    hidden_before = (
        await db_session.execute(
            text(
                "SELECT hidden FROM stations "
                "WHERE rb_uuid='00000000-0000-0000-0000-0000000000cc'",
            ),
        )
    ).scalar_one()
    assert bool(hidden_before) is False

    # Second sync: same row, but RB has renamed it to a spammy form. The
    # update branch must NOT flip hidden, only log a warning.
    respx.reset()
    second = [
        _rb_item(
            stationuuid="00000000-0000-0000-0000-0000000000cc",
            name="# TOP 100 NON-STOP @ Whatever",
        ),
    ]
    respx.get(url__regex=r"https://host-a\.example/.*").respond(json=second)
    client2 = RadioBrowserClient(servers=["host-a.example"])
    await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client2)

    hidden_after = (
        await db_session.execute(
            text(
                "SELECT hidden FROM stations "
                "WHERE rb_uuid='00000000-0000-0000-0000-0000000000cc'",
            ),
        )
    ).scalar_one()
    assert bool(hidden_after) is False  # Still visible; only the operator can hide it.


@respx.mock
async def test_existing_hidden_true_stays_hidden_after_rename(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    # First sync inserts spammy row → hidden=true.
    first = [
        _rb_item(
            stationuuid="00000000-0000-0000-0000-0000000000dd",
            name="# TOP 100 CLUB CHARTS @ blah",
            url="https://stream.example.com/x.mp3?ref=radiobrowser-top100",
        ),
    ]
    respx.get(url__regex=r"https://host-a\.example/.*").respond(json=first)
    client = RadioBrowserClient(servers=["host-a.example"])
    await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)

    hidden_before = (
        await db_session.execute(
            text(
                "SELECT hidden FROM stations "
                "WHERE rb_uuid='00000000-0000-0000-0000-0000000000dd'",
            ),
        )
    ).scalar_one()
    assert bool(hidden_before) is True

    # Second sync: RB cleaned the name, but our hidden flag stays.
    respx.reset()
    second = [
        _rb_item(
            stationuuid="00000000-0000-0000-0000-0000000000dd",
            name="Cleaned Up Radio",
            url="https://stream.example.com/x.mp3",
        ),
    ]
    respx.get(url__regex=r"https://host-a\.example/.*").respond(json=second)
    client2 = RadioBrowserClient(servers=["host-a.example"])
    await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client2)

    hidden_after = (
        await db_session.execute(
            text(
                "SELECT hidden FROM stations "
                "WHERE rb_uuid='00000000-0000-0000-0000-0000000000dd'",
            ),
        )
    ).scalar_one()
    assert bool(hidden_after) is True
