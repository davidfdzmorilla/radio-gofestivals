"""cleanup-clickcount-history · drop snapshots older than retention window."""
from __future__ import annotations

import asyncio

import typer
from sqlalchemy import text

from scripts.db import make_engine, make_sessionmaker
from scripts.logging import get_logger

log = get_logger("cleanup_clickcount_history")
app = typer.Typer(help="radio.gofestivals · cleanup old clickcount snapshots")


async def _run(*, dry_run: bool, retention_days: int) -> None:
    engine = make_engine()
    maker = make_sessionmaker(engine)
    try:
        async with maker() as session:
            if dry_run:
                count = (
                    await session.execute(
                        text(
                            """
                            SELECT count(*) FROM station_clickcount_history
                            WHERE recorded_at < now() - (:d || ' days')::interval
                            """,
                        ),
                        {"d": str(retention_days)},
                    )
                ).scalar_one()
                log.info(
                    "cleanup_dry_run",
                    would_delete=int(count),
                    retention_days=retention_days,
                )
                return

            result = await session.execute(
                text(
                    """
                    DELETE FROM station_clickcount_history
                    WHERE recorded_at < now() - (:d || ' days')::interval
                    RETURNING id
                    """,
                ),
                {"d": str(retention_days)},
            )
            deleted = len(result.all())
            await session.commit()
            log.info(
                "cleanup_done",
                deleted=deleted,
                retention_days=retention_days,
            )
    finally:
        await engine.dispose()


@app.command()
def run(
    dry_run: bool = typer.Option(default=False, help="Don't write."),
    retention_days: int = typer.Option(default=90, help="Keep last N days."),
) -> None:
    """Drop history rows older than retention_days."""
    asyncio.run(_run(dry_run=dry_run, retention_days=retention_days))


if __name__ == "__main__":
    app()
