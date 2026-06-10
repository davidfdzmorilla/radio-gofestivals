"""Plays retention cron (Fase B / B4).

Daily job that:

  1. Aggregates ``station_plays`` rows older than ``--days`` (default 90)
     into ``station_plays_daily(station_id, day, plays)`` via UPSERT. The
     UPSERT adds incoming counts to whatever was previously stored, so
     re-aggregating after a partial failure does not double-count rows
     that were already deleted in the previous pass.
  2. Deletes the aggregated source rows from ``station_plays``.

Both steps run in a single transaction. ``--dry-run`` rolls back instead
of committing and returns the counts that *would* have moved.

Idempotency: running twice in a row yields aggregated_rows=0 on the
second call — the source has already been emptied for the time window.
Crossing midnight UTC re-includes the freshly-eligible day's rows.

Counter side-effect: the AFTER DELETE trigger on station_plays
decrements stations.local_plays_total when retention deletes the source
rows. That column is therefore "plays still in retention" rather than
"plays ever". B5's ranking computes the 7-day window from station_plays
directly, so this drift does not affect ranking. If a strict all-time
counter is needed, it should live in a separate column with its own
maintenance path.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import typer
from sqlalchemy import text

from scripts.db import make_engine, make_sessionmaker
from scripts.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


log = get_logger("retain_plays")
app = typer.Typer(help="radio.gofestivals · plays retention pipeline")


_COUNT_CANDIDATES = text(
    "SELECT COUNT(*) FROM station_plays WHERE played_at < :cutoff",
)

_UPSERT_DAILY = text(
    """
    INSERT INTO station_plays_daily (station_id, day, plays)
    SELECT
        station_id,
        (played_at AT TIME ZONE 'UTC')::date AS day,
        COUNT(*) AS plays
    FROM station_plays
    WHERE played_at < :cutoff
    GROUP BY station_id, day
    ON CONFLICT (station_id, day) DO UPDATE
        SET plays = station_plays_daily.plays + EXCLUDED.plays
    RETURNING 1
    """,
)

_DELETE_OLD = text(
    "DELETE FROM station_plays WHERE played_at < :cutoff RETURNING 1",
)


async def run_retention(
    maker: async_sessionmaker[AsyncSession],
    *,
    days: int,
    dry_run: bool,
) -> dict[str, object]:
    cutoff = datetime.now(tz=UTC) - timedelta(days=days)
    stats: dict[str, object] = {
        "cutoff": cutoff.isoformat(),
        "days": days,
        "dry_run": dry_run,
    }
    async with maker() as session:
        candidates = int(
            (await session.execute(_COUNT_CANDIDATES, {"cutoff": cutoff})).scalar_one(),
        )
        stats["candidate_rows"] = candidates
        if candidates == 0:
            stats["aggregated_groups"] = 0
            stats["deleted_rows"] = 0
            log.info("retain_plays_noop", **stats)
            return stats

        upserted = len(
            (await session.execute(_UPSERT_DAILY, {"cutoff": cutoff})).all(),
        )
        deleted = len(
            (await session.execute(_DELETE_OLD, {"cutoff": cutoff})).all(),
        )
        stats["aggregated_groups"] = upserted
        stats["deleted_rows"] = deleted

        if dry_run:
            await session.rollback()
            log.info("retain_plays_dry_run", **stats)
        else:
            await session.commit()
            log.info("retain_plays_done", **stats)
    return stats


@app.command("run")
def cmd_run(
    days: int = typer.Option(
        90,
        "--days",
        help="Retention window in days. Default 90.",
    ),
    dry_run: bool = typer.Option(  # noqa: FBT001, FBT002
        False,  # noqa: FBT003
        "--dry-run",
        help="Show what would move without committing.",
    ),
) -> None:
    engine = make_engine()
    maker = make_sessionmaker(engine)

    async def _main() -> dict[str, object]:
        try:
            return await run_retention(
                maker,
                days=days,
                dry_run=dry_run,
            )
        finally:
            await engine.dispose()

    asyncio.run(_main())


if __name__ == "__main__":
    app()
