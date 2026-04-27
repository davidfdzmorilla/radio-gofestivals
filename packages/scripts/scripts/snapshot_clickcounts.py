"""snapshot-clickcounts · daily snapshot of stations.clickcount.

One row per station per UTC day in `station_clickcount_history`.
Idempotent: if today's row already exists, the clickcount is updated
in place rather than duplicated. Runs over every status (active,
pending, broken, inactive) so the trend computation later sees the
full population.
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import typer
from sqlalchemy import text

from scripts.db import make_engine, make_sessionmaker
from scripts.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


log = get_logger("snapshot_clickcounts")
app = typer.Typer(help="radio.gofestivals · daily clickcount snapshot")


_TARGET_STATUSES = ("active", "pending", "broken", "inactive")


async def _run(*, dry_run: bool) -> None:
    engine = make_engine()
    maker = make_sessionmaker(engine)
    try:
        async with maker() as session:
            if dry_run:
                count = (
                    await session.execute(
                        text(
                            """
                            SELECT COUNT(*) FROM stations
                            WHERE status::text = ANY(:sts)
                            """,
                        ),
                        {"sts": list(_TARGET_STATUSES)},
                    )
                ).scalar_one()
                log.info("snapshot_dry_run", would_insert=int(count))
                return

            result = await session.execute(
                text(
                    """
                    INSERT INTO station_clickcount_history
                        (station_id, clickcount, recorded_at)
                    SELECT id, clickcount, now()
                    FROM stations
                    WHERE status::text = ANY(:sts)
                    ON CONFLICT (station_id, ((recorded_at AT TIME ZONE 'UTC')::date))
                    DO UPDATE SET
                        clickcount = EXCLUDED.clickcount,
                        recorded_at = EXCLUDED.recorded_at
                    RETURNING id
                    """,
                ),
                {"sts": list(_TARGET_STATUSES)},
            )
            inserted = len(result.all())
            await session.commit()
            log.info("snapshot_done", inserted=inserted)
    finally:
        await engine.dispose()


@app.command()
def run(
    dry_run: bool = typer.Option(default=False, help="Don't write."),
) -> None:
    """Run the daily snapshot."""
    asyncio.run(_run(dry_run=dry_run))


if __name__ == "__main__":
    app()
