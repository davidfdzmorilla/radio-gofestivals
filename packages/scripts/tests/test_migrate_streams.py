from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import text

from scripts.migrate_streams import migrate_run

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def _insert(
    session: AsyncSession,
    *,
    name: str,
    slug: str,
    stream_url: str,
    bitrate: int,
    codec: str,
    status: str = "active",
    homepage: str | None = "https://example.com",
    country: str = "ES",
) -> uuid.UUID:
    result = await session.execute(
        text(
            """
            INSERT INTO stations
                (name, slug, stream_url, homepage_url, country_code,
                 bitrate, codec, quality_score, status, source)
            VALUES
                (:name, :slug, :stream, :hp, :cc,
                 :br, :codec, 50, CAST(:st AS station_status), 'radio-browser')
            RETURNING id
            """,
        ),
        {
            "name": name, "slug": slug, "stream": stream_url, "hp": homepage,
            "cc": country, "br": bitrate, "codec": codec, "st": status,
        },
    )
    sid = result.scalar_one()
    await session.commit()
    return sid


async def test_lone_station_gets_one_primary_stream(db_session: AsyncSession) -> None:
    sid = await _insert(
        db_session, name="Solo FM", slug="solo",
        stream_url="https://s/solo.mp3", bitrate=128, codec="mp3",
    )

    stats = await migrate_run(db_session, dry_run=False)

    assert stats.stations_kept_as_brand == 1
    assert stats.streams_created == 1
    assert stats.primary_streams_assigned == 1

    streams = (
        await db_session.execute(
            text(
                "SELECT stream_url, is_primary FROM station_streams "
                "WHERE station_id = :sid",
            ),
            {"sid": sid},
        )
    ).all()
    assert len(streams) == 1
    assert streams[0][1] is True


async def test_group_collapses_duplicates_into_streams(db_session: AsyncSession) -> None:
    keeper = await _insert(
        db_session, name="Sub FM", slug="sub-1",
        stream_url="https://s/sub-hi.aac", bitrate=320, codec="aac+",
        status="active",
    )
    dup1 = await _insert(
        db_session, name="Sub FM", slug="sub-2",
        stream_url="https://s/sub-mid.mp3", bitrate=128, codec="mp3",
        status="duplicate",
    )
    dup2 = await _insert(
        db_session, name="Sub FM", slug="sub-3",
        stream_url="https://s/sub-low.mp3", bitrate=64, codec="mp3",
        status="duplicate",
    )

    stats = await migrate_run(db_session, dry_run=False)

    assert stats.stations_kept_as_brand == 1
    assert stats.stations_marked_inactive_after_merge == 2
    assert stats.streams_created == 3
    assert stats.primary_streams_assigned == 1

    statuses = dict(
        (
            await db_session.execute(
                text("SELECT id, status FROM stations WHERE id IN (:a, :b, :c)"),
                {"a": keeper, "b": dup1, "c": dup2},
            )
        ).all(),
    )
    assert statuses[keeper] == "active"
    assert statuses[dup1] == "inactive"
    assert statuses[dup2] == "inactive"

    streams = (
        await db_session.execute(
            text(
                "SELECT stream_url, is_primary, bitrate, codec "
                "FROM station_streams WHERE station_id = :sid "
                "ORDER BY is_primary DESC, bitrate DESC",
            ),
            {"sid": keeper},
        )
    ).all()
    assert len(streams) == 3
    # Highest technical (320 + aac+) wins primary.
    assert streams[0][1] is True
    assert streams[0][2] == 320
    assert streams[0][3] == "aac+"
    primaries = sum(1 for s in streams if s[1])
    assert primaries == 1


async def test_dry_run_does_not_mutate(db_session: AsyncSession) -> None:
    await _insert(
        db_session, name="Quiet FM", slug="quiet",
        stream_url="https://s/q.mp3", bitrate=128, codec="mp3",
    )

    stats = await migrate_run(db_session, dry_run=True)
    assert stats.streams_created == 1

    count = (
        await db_session.execute(text("SELECT COUNT(*) FROM station_streams"))
    ).scalar_one()
    assert count == 0


async def test_promotes_orphan_duplicate_group(db_session: AsyncSession) -> None:
    # Group of two duplicates with no active brand: should promote highest.
    a = await _insert(
        db_session, name="Orphan FM", slug="orph-a",
        stream_url="https://s/o-hi.mp3", bitrate=192, codec="mp3",
        status="duplicate",
    )
    b = await _insert(
        db_session, name="Orphan FM", slug="orph-b",
        stream_url="https://s/o-low.mp3", bitrate=64, codec="mp3",
        status="duplicate",
    )

    stats = await migrate_run(db_session, dry_run=False)

    assert stats.stations_promoted_from_duplicate == 1

    statuses = dict(
        (
            await db_session.execute(
                text("SELECT id, status FROM stations WHERE id IN (:a, :b)"),
                {"a": a, "b": b},
            )
        ).all(),
    )
    # Higher-bitrate row was promoted.
    assert statuses[a] == "active"
    assert statuses[b] == "inactive"


async def test_idempotent_second_run_no_duplicates(db_session: AsyncSession) -> None:
    sid = await _insert(
        db_session, name="Repeat FM", slug="rep",
        stream_url="https://s/rep.mp3", bitrate=128, codec="mp3",
    )

    await migrate_run(db_session, dry_run=False)
    await migrate_run(db_session, dry_run=False)

    count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM station_streams WHERE station_id = :sid"),
            {"sid": sid},
        )
    ).scalar_one()
    assert count == 1
