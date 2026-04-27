from __future__ import annotations

import math
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import text

from scripts.cleanup_clickcount_history import _run as cleanup_run
from scripts.compute_click_trends import _run as compute_trends_run
from scripts.snapshot_clickcounts import _run as snapshot_run

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def _seed_station(
    db_session: AsyncSession,
    *,
    slug: str,
    clickcount: int,
    status: str = "active",
) -> str:
    sid = (
        await db_session.execute(
            text(
                """
                INSERT INTO stations
                    (slug, name, status, clickcount)
                VALUES (:slug, :slug,
                        CAST(:st AS station_status), :cc)
                RETURNING id::text
                """,
            ),
            {"slug": slug, "st": status, "cc": clickcount},
        )
    ).scalar_one()
    await db_session.commit()
    return str(sid)


async def _seed_history_at(
    db_session: AsyncSession,
    *,
    station_id: str,
    clickcount: int,
    days_ago: float,
) -> None:
    await db_session.execute(
        text(
            """
            INSERT INTO station_clickcount_history
                (station_id, clickcount, recorded_at)
            VALUES
                (:sid, :cc, now() - (:d || ' days')::interval)
            """,
        ),
        {"sid": station_id, "cc": clickcount, "d": str(days_ago)},
    )
    await db_session.commit()


# --- snapshot-clickcounts ---------------------------------------------------


async def test_snapshot_creates_one_row_per_active_station(
    db_session: AsyncSession,
) -> None:
    a = await _seed_station(db_session, slug="snap-a", clickcount=100)
    b = await _seed_station(db_session, slug="snap-b", clickcount=200)

    await snapshot_run(dry_run=False)

    counts = dict(
        (
            await db_session.execute(
                text(
                    "SELECT station_id::text, count(*) "
                    "FROM station_clickcount_history "
                    "WHERE station_id IN (CAST(:a AS uuid), CAST(:b AS uuid)) "
                    "GROUP BY station_id",
                ),
                {"a": a, "b": b},
            )
        ).all(),
    )
    assert counts == {a: 1, b: 1}


async def test_snapshot_is_idempotent_same_day(
    db_session: AsyncSession,
) -> None:
    sid = await _seed_station(db_session, slug="snap-idem", clickcount=100)
    await snapshot_run(dry_run=False)
    # Bump the live counter and snapshot again on the same UTC day
    await db_session.execute(
        text("UPDATE stations SET clickcount = 250 WHERE id = CAST(:s AS uuid)"),
        {"s": sid},
    )
    await db_session.commit()
    await snapshot_run(dry_run=False)

    rows = (
        await db_session.execute(
            text(
                "SELECT count(*), max(clickcount) "
                "FROM station_clickcount_history "
                "WHERE station_id = CAST(:s AS uuid)",
            ),
            {"s": sid},
        )
    ).first()
    assert rows is not None
    assert int(rows[0]) == 1  # ON CONFLICT DO UPDATE, no duplicate
    assert int(rows[1]) == 250


async def test_snapshot_dry_run_does_not_write(
    db_session: AsyncSession,
) -> None:
    await _seed_station(db_session, slug="snap-dry", clickcount=10)
    await snapshot_run(dry_run=True)

    count = (
        await db_session.execute(
            text("SELECT count(*) FROM station_clickcount_history"),
        )
    ).scalar_one()
    assert int(count) == 0


# --- compute-click-trends ---------------------------------------------------


async def test_compute_trends_log_ratio(db_session: AsyncSession) -> None:
    growing = await _seed_station(db_session, slug="t-grow", clickcount=200)
    flat = await _seed_station(db_session, slug="t-flat", clickcount=50)
    no_hist = await _seed_station(db_session, slug="t-none", clickcount=10)

    # Snapshot 7 days ago for the first two; nothing for no_hist.
    await _seed_history_at(
        db_session, station_id=growing, clickcount=100, days_ago=7,
    )
    await _seed_history_at(
        db_session, station_id=flat, clickcount=50, days_ago=7,
    )

    await compute_trends_run(dry_run=False)

    trends = dict(
        (
            await db_session.execute(
                text(
                    "SELECT id::text, click_trend FROM stations "
                    "WHERE id IN (CAST(:a AS uuid), CAST(:b AS uuid), CAST(:c AS uuid))",
                ),
                {"a": growing, "b": flat, "c": no_hist},
            )
        ).all(),
    )

    expected_grow = math.log(201) - math.log(101)  # ≈ 0.6884
    assert abs(float(trends[growing]) - expected_grow) < 0.001
    assert abs(float(trends[flat])) < 0.001
    assert trends[no_hist] == Decimal("0.0000")


async def test_compute_trends_handles_no_data(db_session: AsyncSession) -> None:
    """Running on an empty table must not crash."""
    await compute_trends_run(dry_run=False)


# --- cleanup-clickcount-history --------------------------------------------


async def test_cleanup_deletes_rows_beyond_retention(
    db_session: AsyncSession,
) -> None:
    sid = await _seed_station(db_session, slug="cl-a", clickcount=1)
    await _seed_history_at(db_session, station_id=sid, clickcount=1, days_ago=100)
    await _seed_history_at(db_session, station_id=sid, clickcount=2, days_ago=89)
    await _seed_history_at(db_session, station_id=sid, clickcount=3, days_ago=30)

    await cleanup_run(dry_run=False, retention_days=90)

    remaining = (
        await db_session.execute(
            text(
                "SELECT clickcount FROM station_clickcount_history "
                "WHERE station_id = CAST(:s AS uuid) ORDER BY clickcount",
            ),
            {"s": sid},
        )
    ).all()
    assert [int(r[0]) for r in remaining] == [2, 3]


async def test_cleanup_dry_run_keeps_data(
    db_session: AsyncSession,
) -> None:
    sid = await _seed_station(db_session, slug="cl-dry", clickcount=1)
    await _seed_history_at(db_session, station_id=sid, clickcount=1, days_ago=200)
    await cleanup_run(dry_run=True, retention_days=90)
    count = (
        await db_session.execute(
            text(
                "SELECT count(*) FROM station_clickcount_history "
                "WHERE station_id = CAST(:s AS uuid)",
            ),
            {"s": sid},
        )
    ).scalar_one()
    assert int(count) == 1
