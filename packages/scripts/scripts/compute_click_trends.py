"""compute-click-trends · 7-day log-ratio trend per station.

For each station with status in {active, pending, broken}, looks up
the snapshot closest to NOW() - 7 days (within a ±1 day window) and
computes:

    click_trend = ln(current_clickcount + 1)
                - ln(historical_clickcount + 1)

The window is symmetric to absorb cron drift: a snapshot taken at
04:15 UTC each day will have its 7-day-ago row land somewhere between
6 and 8 days in the past. Stations without any qualifying snapshot
get click_trend = 0.

Single SQL UPDATE so we don't loop in Python over ~1400 rows; the
DISTINCT ON picks the row whose age is closest to exactly 7 days.
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import typer
from sqlalchemy import text

from scripts.db import make_engine, make_sessionmaker
from scripts.logging import get_logger

if TYPE_CHECKING:
    pass


log = get_logger("compute_click_trends")
app = typer.Typer(help="radio.gofestivals · compute 7-day click_trend")


_UPDATE_SQL = text(
    """
    WITH historical AS (
        SELECT DISTINCT ON (station_id)
            station_id,
            clickcount AS clickcount_7d_ago
        FROM station_clickcount_history
        WHERE recorded_at >= now() - INTERVAL '8 days'
          AND recorded_at <= now() - INTERVAL '6 days'
        ORDER BY
            station_id,
            ABS(EXTRACT(EPOCH FROM (recorded_at - (now() - INTERVAL '7 days'))))
    ),
    upd AS (
        UPDATE stations s
        SET click_trend = (
            LN(s.clickcount + 1) - LN(h.clickcount_7d_ago + 1)
        )::numeric(10, 4)
        FROM historical h
        WHERE h.station_id = s.id
          AND s.status IN ('active', 'pending', 'broken')
        RETURNING s.id, s.click_trend
    ),
    reset AS (
        UPDATE stations s
        SET click_trend = 0.0000
        WHERE s.status IN ('active', 'pending', 'broken')
          AND NOT EXISTS (SELECT 1 FROM historical h WHERE h.station_id = s.id)
          AND s.click_trend != 0.0000
        RETURNING s.id
    )
    SELECT
        (SELECT count(*) FROM upd) AS updated,
        (SELECT count(*) FROM reset) AS reset_to_zero,
        (SELECT max(click_trend) FROM upd) AS max_trend,
        (SELECT min(click_trend) FROM upd) AS min_trend
    """,
)


_STATS_SQL = text(
    """
    SELECT count(*)
    FROM stations
    WHERE status IN ('active', 'pending', 'broken')
    """,
)


async def _run(*, dry_run: bool) -> None:
    engine = make_engine()
    maker = make_sessionmaker(engine)
    try:
        async with maker() as session:
            scanned = (await session.execute(_STATS_SQL)).scalar_one()

            if dry_run:
                # Count how many would receive a non-zero trend.
                preview = (
                    await session.execute(
                        text(
                            """
                            SELECT count(*)
                            FROM stations s
                            WHERE s.status IN ('active', 'pending', 'broken')
                              AND EXISTS (
                                  SELECT 1
                                  FROM station_clickcount_history h
                                  WHERE h.station_id = s.id
                                    AND h.recorded_at >= now() - INTERVAL '8 days'
                                    AND h.recorded_at <= now() - INTERVAL '6 days'
                              )
                            """,
                        ),
                    )
                ).scalar_one()
                log.info(
                    "compute_trends_dry_run",
                    scanned=int(scanned),
                    would_update=int(preview),
                    no_history=int(scanned) - int(preview),
                )
                return

            row = (await session.execute(_UPDATE_SQL)).first()
            await session.commit()

            updated = int(row[0]) if row else 0
            reset_to_zero = int(row[1]) if row else 0
            max_trend = float(row[2]) if row and row[2] is not None else None
            min_trend = float(row[3]) if row and row[3] is not None else None
            log.info(
                "compute_trends_done",
                scanned=int(scanned),
                updated=updated,
                no_history=int(scanned) - updated,
                reset_to_zero=reset_to_zero,
                max_trend=max_trend,
                min_trend=min_trend,
            )
    finally:
        await engine.dispose()


@app.command()
def run(
    dry_run: bool = typer.Option(default=False, help="Don't write."),
) -> None:
    """Compute click_trend from the 7-day history."""
    asyncio.run(_run(dry_run=dry_run))


if __name__ == "__main__":
    app()
