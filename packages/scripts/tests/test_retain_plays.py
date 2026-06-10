from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import text

from scripts.retain_plays import run_retention

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def _make_station(session: AsyncSession, slug: str) -> uuid.UUID:
    sid = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO stations (id, slug, name, status, hidden, curated, quality_score)
            VALUES (:id, :slug, :name, 'active', false, true, 80)
            """,
        ),
        {"id": sid, "slug": slug, "name": slug},
    )
    await session.commit()
    return sid


async def _insert_play(
    session: AsyncSession,
    *,
    station_id: uuid.UUID,
    played_at: datetime,
    client_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> None:
    cid = client_id or uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO station_plays (station_id, client_id, user_id, played_at) "
            "VALUES (:sid, :cid, :uid, :pa)",
        ),
        {
            "sid": station_id,
            "cid": cid if user_id is None else None,
            "uid": user_id,
            "pa": played_at,
        },
    )
    await session.commit()


async def _count(session: AsyncSession, table: str) -> int:
    return int(
        (await session.execute(text(f"SELECT COUNT(*) FROM {table}"))).scalar_one(),
    )


async def _daily_row(
    session: AsyncSession,
    station_id: uuid.UUID,
    day: date,
) -> int | None:
    row = (
        await session.execute(
            text(
                "SELECT plays FROM station_plays_daily WHERE station_id = :sid AND day = :d",
            ),
            {"sid": station_id, "d": day},
        )
    ).first()
    return int(row[0]) if row else None


async def test_noop_when_nothing_old(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    sid = await _make_station(db_session, "fresh")
    await _insert_play(
        db_session,
        station_id=sid,
        played_at=datetime.now(tz=UTC) - timedelta(days=10),
    )

    stats = await run_retention(maker, days=90, dry_run=False)

    assert stats["candidate_rows"] == 0
    assert stats["aggregated_groups"] == 0
    assert stats["deleted_rows"] == 0
    assert await _count(db_session, "station_plays") == 1
    assert await _count(db_session, "station_plays_daily") == 0


async def test_old_rows_aggregate_and_delete(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    sid = await _make_station(db_session, "old")
    base = datetime.now(tz=UTC) - timedelta(days=100)
    # Three plays on the same UTC day, plus one on the next day.
    for _ in range(3):
        await _insert_play(db_session, station_id=sid, played_at=base)
    await _insert_play(
        db_session,
        station_id=sid,
        played_at=base + timedelta(days=1),
    )

    stats = await run_retention(maker, days=90, dry_run=False)

    assert stats["candidate_rows"] == 4
    assert stats["aggregated_groups"] == 2
    assert stats["deleted_rows"] == 4
    assert await _count(db_session, "station_plays") == 0
    assert await _count(db_session, "station_plays_daily") == 2
    day1 = base.astimezone(UTC).date()
    day2 = (base + timedelta(days=1)).astimezone(UTC).date()
    assert await _daily_row(db_session, sid, day1) == 3
    assert await _daily_row(db_session, sid, day2) == 1


async def test_recent_rows_untouched(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    sid = await _make_station(db_session, "mixed")
    old = datetime.now(tz=UTC) - timedelta(days=100)
    recent = datetime.now(tz=UTC) - timedelta(days=10)
    for _ in range(2):
        await _insert_play(db_session, station_id=sid, played_at=old)
    for _ in range(3):
        await _insert_play(db_session, station_id=sid, played_at=recent)

    await run_retention(maker, days=90, dry_run=False)

    assert await _count(db_session, "station_plays") == 3
    assert await _count(db_session, "station_plays_daily") == 1


async def test_dry_run_rolls_back(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    sid = await _make_station(db_session, "dry")
    for _ in range(5):
        await _insert_play(
            db_session,
            station_id=sid,
            played_at=datetime.now(tz=UTC) - timedelta(days=100),
        )

    stats = await run_retention(maker, days=90, dry_run=True)

    assert stats["candidate_rows"] == 5
    assert stats["deleted_rows"] == 5
    assert stats["aggregated_groups"] == 1
    # ... but the source is untouched and the aggregate is empty.
    assert await _count(db_session, "station_plays") == 5
    assert await _count(db_session, "station_plays_daily") == 0


async def test_idempotent_second_run_is_noop(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    sid = await _make_station(db_session, "twice")
    base = datetime.now(tz=UTC) - timedelta(days=100)
    for _ in range(4):
        await _insert_play(db_session, station_id=sid, played_at=base)

    first = await run_retention(maker, days=90, dry_run=False)
    second = await run_retention(maker, days=90, dry_run=False)

    assert first["deleted_rows"] == 4
    assert second["candidate_rows"] == 0
    assert second["deleted_rows"] == 0
    assert await _count(db_session, "station_plays_daily") == 1
    day = base.astimezone(UTC).date()
    assert await _daily_row(db_session, sid, day) == 4


async def test_upsert_accumulates_across_runs(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    """If new plays from the same (station, day) appear after the first
    retention pass (e.g. retroactive backfill), the next pass adds them
    on top of the existing aggregate rather than replacing it.
    """
    sid = await _make_station(db_session, "accum")
    base = datetime.now(tz=UTC) - timedelta(days=100)
    for _ in range(2):
        await _insert_play(db_session, station_id=sid, played_at=base)
    await run_retention(maker, days=90, dry_run=False)
    day = base.astimezone(UTC).date()
    assert await _daily_row(db_session, sid, day) == 2

    # Two new plays land in the same already-aggregated day.
    for _ in range(2):
        await _insert_play(db_session, station_id=sid, played_at=base)
    await run_retention(maker, days=90, dry_run=False)
    assert await _daily_row(db_session, sid, day) == 4


async def test_decrements_local_plays_total_via_trigger(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    """B2's DELETE trigger fires on retention deletes, so the
    denormalized counter reflects "plays still in the retention window".
    The migration comment documents this; the test pins the contract.
    """
    sid = await _make_station(db_session, "counter")
    await _insert_play(
        db_session,
        station_id=sid,
        played_at=datetime.now(tz=UTC) - timedelta(days=100),
    )
    counter_before = (
        await db_session.execute(
            text(
                "SELECT local_plays_total FROM stations WHERE id = :id",
            ),
            {"id": sid},
        )
    ).scalar_one()
    assert int(counter_before) == 1

    await run_retention(maker, days=90, dry_run=False)

    counter_after = (
        await db_session.execute(
            text(
                "SELECT local_plays_total FROM stations WHERE id = :id",
            ),
            {"id": sid},
        )
    ).scalar_one()
    assert int(counter_after) == 0
