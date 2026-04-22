from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import httpx
import pytest
import respx
from sqlalchemy import text

from scripts.rb_client import RadioBrowserClient
from scripts.rb_sync import run_health_check, run_sync

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def _rb_items(overrides: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    base = [
        {
            "stationuuid": "00000000-0000-0000-0000-000000000001",
            "name": "Techno Tribe",
            "url": "https://stream.example.com/tt.mp3",
            "url_resolved": "https://stream.example.com/tt.mp3",
            "countrycode": "es",
            "state": "Madrid",
            "codec": "MP3",
            "bitrate": 128,
            "language": "spanish",
            "tags": "techno,electronic,minimal techno",
            "geo_lat": 40.4168,
            "geo_long": -3.7038,
        },
        {
            "stationuuid": "00000000-0000-0000-0000-000000000002",
            "name": "Deep Vibes",
            "url": "https://stream.example.com/dv.mp3",
            "url_resolved": "https://stream.example.com/dv.mp3",
            "countrycode": "de",
            "state": "Berlin",
            "codec": "aac",
            "bitrate": 192,
            "language": "german",
            "tags": "deep house,house",
        },
    ]
    return base + (overrides or [])


@respx.mock
async def _patch_rb(items: list[dict[str, Any]]) -> RadioBrowserClient:
    respx.get(url__regex=r"https://host-a\.example/json/stations/search.*").respond(
        json=items,
    )
    return RadioBrowserClient(servers=["host-a.example"])


@respx.mock
async def test_full_sync_with_mocked_rb(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    respx.get(url__regex=r"https://host-a\.example/.*").respond(json=_rb_items())
    client = RadioBrowserClient(servers=["host-a.example"])

    stats = await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)
    assert stats.inserted == 2
    assert stats.errors == 0

    count = (await db_session.execute(text("SELECT COUNT(*) FROM stations"))).scalar_one()
    assert count == 2
    sg = (await db_session.execute(text("SELECT COUNT(*) FROM station_genres"))).scalar_one()
    assert sg >= 2


@respx.mock
async def test_idempotent_two_runs(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    respx.get(url__regex=r"https://host-a\.example/.*").respond(json=_rb_items())

    client1 = RadioBrowserClient(servers=["host-a.example"])
    stats1 = await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client1)

    count_after_1 = (
        await db_session.execute(text("SELECT COUNT(*) FROM stations"))
    ).scalar_one()
    sg_after_1 = (
        await db_session.execute(text("SELECT COUNT(*) FROM station_genres"))
    ).scalar_one()
    last_sync_1 = (
        await db_session.execute(
            text(
                "SELECT last_sync_at FROM stations "
                "WHERE rb_uuid = '00000000-0000-0000-0000-000000000001'",
            ),
        )
    ).scalar_one()

    client2 = RadioBrowserClient(servers=["host-a.example"])
    stats2 = await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client2)

    count_after_2 = (
        await db_session.execute(text("SELECT COUNT(*) FROM stations"))
    ).scalar_one()
    sg_after_2 = (
        await db_session.execute(text("SELECT COUNT(*) FROM station_genres"))
    ).scalar_one()
    last_sync_2 = (
        await db_session.execute(
            text(
                "SELECT last_sync_at FROM stations "
                "WHERE rb_uuid = '00000000-0000-0000-0000-000000000001'",
            ),
        )
    ).scalar_one()

    assert stats1.inserted == 2
    assert stats1.updated == 0
    assert stats2.inserted == 0
    assert stats2.updated == 2

    assert count_after_2 == count_after_1 == 2
    assert sg_after_2 == sg_after_1
    assert last_sync_2 > last_sync_1


@respx.mock
async def test_preserves_broken_status(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    rb_uuid = "00000000-0000-0000-0000-000000000001"
    await db_session.execute(
        text(
            """
            INSERT INTO stations (
                rb_uuid, slug, name, stream_url, status, failed_checks
            ) VALUES (
                :rb, 'techno-tribe', 'Techno Tribe',
                'https://stream.example.com/tt.mp3', 'broken', 5
            )
            """,
        ),
        {"rb": rb_uuid},
    )
    await db_session.commit()

    respx.get(url__regex=r"https://host-a\.example/.*").respond(json=_rb_items())
    client = RadioBrowserClient(servers=["host-a.example"])
    await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)

    row = (
        await db_session.execute(
            text(
                "SELECT status::text, failed_checks FROM stations WHERE rb_uuid = :rb",
            ),
            {"rb": rb_uuid},
        )
    ).first()
    assert row is not None
    assert row[0] == "broken"
    assert row[1] == 5


@respx.mock
async def test_skips_hls_uppercase(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    items = [
        {
            "stationuuid": str(uuid.uuid4()),
            "name": "HLS upper",
            "url": "https://stream.example.com/live.M3U8",
            "url_resolved": "https://stream.example.com/live.M3U8",
            "tags": "techno",
        },
    ]
    respx.get(url__regex=r"https://host-a\.example/.*").respond(json=items)
    client = RadioBrowserClient(servers=["host-a.example"])
    stats = await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)

    assert stats.skipped_hls == 1
    count = (await db_session.execute(text("SELECT COUNT(*) FROM stations"))).scalar_one()
    assert count == 0


@respx.mock
async def test_skips_hls_with_query(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    items = [
        {
            "stationuuid": str(uuid.uuid4()),
            "name": "HLS query",
            "url": "https://stream.example.com/live.m3u8?token=xxx",
            "url_resolved": "https://stream.example.com/live.m3u8?token=xxx",
            "tags": "techno",
        },
    ]
    respx.get(url__regex=r"https://host-a\.example/.*").respond(json=items)
    client = RadioBrowserClient(servers=["host-a.example"])
    stats = await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)

    assert stats.skipped_hls == 1
    count = (await db_session.execute(text("SELECT COUNT(*) FROM stations"))).scalar_one()
    assert count == 0


@respx.mock
async def test_skips_hls_with_fragment(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    items = [
        {
            "stationuuid": str(uuid.uuid4()),
            "name": "HLS frag",
            "url": "https://stream.example.com/live.m3u8#section",
            "url_resolved": "https://stream.example.com/live.m3u8#section",
            "tags": "techno",
        },
    ]
    respx.get(url__regex=r"https://host-a\.example/.*").respond(json=items)
    client = RadioBrowserClient(servers=["host-a.example"])
    stats = await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)

    assert stats.skipped_hls == 1
    count = (await db_session.execute(text("SELECT COUNT(*) FROM stations"))).scalar_one()
    assert count == 0


@respx.mock
async def test_preserves_curated_flag_and_status(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    respx.get(url__regex=r"https://host-a\.example/.*").respond(json=_rb_items())
    client = RadioBrowserClient(servers=["host-a.example"])
    await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)

    await db_session.execute(
        text(
            """
            UPDATE stations SET curated = true, quality_score = 99, status = 'active'
            WHERE rb_uuid = '00000000-0000-0000-0000-000000000001'
            """,
        ),
    )
    await db_session.commit()

    client = RadioBrowserClient(servers=["host-a.example"])
    await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)

    row = (
        await db_session.execute(
            text(
                "SELECT curated, quality_score, status::text FROM stations "
                "WHERE rb_uuid='00000000-0000-0000-0000-000000000001'",
            ),
        )
    ).first()
    assert row is not None
    assert row[0] is True
    assert row[1] == 99
    assert row[2] == "active"


@respx.mock
async def test_preserves_manual_station_genres(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    respx.get(url__regex=r"https://host-a\.example/.*").respond(json=_rb_items())
    client = RadioBrowserClient(servers=["host-a.example"])
    await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)

    station_id = (
        await db_session.execute(
            text("SELECT id FROM stations WHERE rb_uuid='00000000-0000-0000-0000-000000000001'"),
        )
    ).scalar_one()

    trance_id = (
        await db_session.execute(text("SELECT id FROM genres WHERE slug='trance'"))
    ).scalar_one()
    await db_session.execute(
        text(
            """
            INSERT INTO station_genres (station_id, genre_id, source, confidence)
            VALUES (:sid, :gid, 'manual', 100)
            """,
        ),
        {"sid": str(station_id), "gid": trance_id},
    )
    await db_session.commit()

    client = RadioBrowserClient(servers=["host-a.example"])
    await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)

    row = (
        await db_session.execute(
            text(
                "SELECT COUNT(*) FROM station_genres "
                "WHERE station_id = :sid AND source = 'manual'",
            ),
            {"sid": str(station_id)},
        )
    ).scalar_one()
    assert row == 1


@respx.mock
async def test_skips_invalid_stream_urls(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    items = [
        {
            "stationuuid": str(uuid.uuid4()),
            "name": "Empty URL",
            "url": "",
            "url_resolved": "",
            "tags": "techno",
        },
        {
            "stationuuid": str(uuid.uuid4()),
            "name": "Bad scheme",
            "url": "ftp://bad/x",
            "url_resolved": "ftp://bad/x",
            "tags": "techno",
        },
    ]
    respx.get(url__regex=r"https://host-a\.example/.*").respond(json=items)
    client = RadioBrowserClient(servers=["host-a.example"])
    stats = await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)

    assert stats.skipped_empty_url == 2
    count = (await db_session.execute(text("SELECT COUNT(*) FROM stations"))).scalar_one()
    assert count == 0


@respx.mock
async def test_skips_hls_streams(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    items = [
        {
            "stationuuid": str(uuid.uuid4()),
            "name": "HLS",
            "url": "https://stream.example.com/live.m3u8",
            "url_resolved": "https://stream.example.com/live.m3u8",
            "tags": "techno",
        },
    ]
    respx.get(url__regex=r"https://host-a\.example/.*").respond(json=items)
    client = RadioBrowserClient(servers=["host-a.example"])
    stats = await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)

    assert stats.skipped_hls == 1
    count = (await db_session.execute(text("SELECT COUNT(*) FROM stations"))).scalar_one()
    assert count == 0


@respx.mock
async def test_slug_collision_handling(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    items = [
        {
            "stationuuid": str(uuid.uuid4()),
            "name": "Tech Tribe",
            "url": "https://s.example.com/a.mp3",
            "url_resolved": "https://s.example.com/a.mp3",
            "tags": "techno",
        },
        {
            "stationuuid": str(uuid.uuid4()),
            "name": "Tech   Tribe",
            "url": "https://s.example.com/b.mp3",
            "url_resolved": "https://s.example.com/b.mp3",
            "tags": "techno",
        },
    ]
    respx.get(url__regex=r"https://host-a\.example/.*").respond(json=items)
    client = RadioBrowserClient(servers=["host-a.example"])
    stats = await run_sync(maker, tag="techno", dry_run=False, limit=500, client=client)

    assert stats.inserted == 2
    assert stats.slug_collisions == 1
    slugs = sorted(
        str(r[0])
        for r in (await db_session.execute(text("SELECT slug FROM stations"))).all()
    )
    assert slugs == ["tech-tribe", "tech-tribe-2"]


@respx.mock
async def test_dry_run_no_writes(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    respx.get(url__regex=r"https://host-a\.example/.*").respond(json=_rb_items())
    client = RadioBrowserClient(servers=["host-a.example"])
    stats = await run_sync(maker, tag="techno", dry_run=True, limit=500, client=client)

    assert stats.inserted == 2
    count = (await db_session.execute(text("SELECT COUNT(*) FROM stations"))).scalar_one()
    assert count == 0


@pytest.mark.usefixtures("db_session")
@respx.mock
async def test_health_check_marks_broken(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        text(
            """
            INSERT INTO stations (slug, name, stream_url, status, failed_checks)
            VALUES ('bad', 'Bad', 'https://bad.example/x.mp3', 'active', 2)
            """,
        ),
    )
    await db_session.commit()

    respx.head(url__regex=r"https://bad\.example/.*").respond(status_code=500)

    async with httpx.AsyncClient() as hc:
        stats = await run_health_check(maker, timeout=2, client=hc)

    assert stats["marked_broken"] == 1
    status = (
        await db_session.execute(text("SELECT status::text FROM stations WHERE slug='bad'"))
    ).scalar_one()
    assert status == "broken"


@pytest.mark.usefixtures("db_session")
@respx.mock
async def test_health_check_recovers(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        text(
            """
            INSERT INTO stations (slug, name, stream_url, status, failed_checks)
            VALUES ('rec', 'Rec', 'https://ok.example/x.mp3', 'broken', 5)
            """,
        ),
    )
    await db_session.commit()

    respx.head(url__regex=r"https://ok\.example/.*").respond(status_code=200)

    async with httpx.AsyncClient() as hc:
        stats = await run_health_check(maker, timeout=2, client=hc)

    assert stats["recovered"] == 1
    row = (
        await db_session.execute(
            text("SELECT status::text, failed_checks FROM stations WHERE slug='rec'"),
        )
    ).first()
    assert row is not None
    assert row[0] == "active"
    assert row[1] == 0
