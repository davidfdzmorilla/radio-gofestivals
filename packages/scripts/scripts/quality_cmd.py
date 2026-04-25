"""compute-quality-scores · CLI command.

Recompute quality_score for stations already in the DB. Useful for
backfill (the column historically defaulted to 50 for every row) and
for nightly reruns after the fail_checks column shifts.

Note: clickcount and votes are not persisted in our `stations` table
(they're Radio-Browser fields the rb_sync flow consumes but doesn't
store). For backfill those signals are absent and `popularity_score`
collapses to 0 — the next `rb_sync` run will refresh the score with
fresh popularity data.
"""
from __future__ import annotations

import asyncio
import statistics
from typing import TYPE_CHECKING

import typer
from sqlalchemy import text

from scripts.db import make_engine, make_sessionmaker
from scripts.logging import get_logger
from scripts.quality import compute_quality_score

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


log = get_logger("compute_quality_scores")
app = typer.Typer(help="radio.gofestivals · backfill quality_score")

_BATCH_SIZE = 100


async def _fetch_rows(
    session: AsyncSession,
    *,
    where_status: str | None,
    limit: int | None,
) -> list[dict[str, object]]:
    where = ""
    params: dict[str, object] = {}
    if where_status:
        where = "WHERE status = CAST(:st AS station_status)"
        params["st"] = where_status
    sql = (
        "SELECT id::text AS id, bitrate, codec, failed_checks, status, "
        "       quality_score "
        f"FROM stations {where} ORDER BY created_at"
    )
    if limit is not None:
        sql += " LIMIT :limit"
        params["limit"] = limit
    result = await session.execute(text(sql), params)
    return [dict(r._mapping) for r in result.all()]  # noqa: SLF001


async def _apply_updates(
    session: AsyncSession,
    pairs: list[tuple[str, int]],
) -> None:
    for i in range(0, len(pairs), _BATCH_SIZE):
        chunk = pairs[i : i + _BATCH_SIZE]
        ids = [pid for pid, _ in chunk]
        scores = [s for _, s in chunk]
        await session.execute(
            text(
                """
                UPDATE stations AS s
                SET quality_score = u.score
                FROM unnest(CAST(:ids AS uuid[]), CAST(:scores AS smallint[]))
                     AS u(id, score)
                WHERE s.id = u.id
                """,
            ),
            {"ids": ids, "scores": scores},
        )
    await session.commit()


@app.command()
def compute_quality_scores(
    dry_run: bool = typer.Option(
        default=False,
        help="Log what would change without writing.",
    ),
    limit: int | None = typer.Option(
        default=None,
        help="Process at most N stations (debug).",
    ),
    where_status: str = typer.Option(
        default="active",
        help="Only stations with this status. Empty string for all.",
    ),
) -> None:
    """Recompute quality_score for existing stations."""
    status_filter: str | None = where_status or None

    async def _main() -> None:
        engine = make_engine()
        maker = make_sessionmaker(engine)
        try:
            async with maker() as session:
                rows = await _fetch_rows(
                    session, where_status=status_filter, limit=limit,
                )
                changed: list[tuple[str, int]] = []
                unchanged = 0
                new_scores: list[int] = []
                for row in rows:
                    new_score = compute_quality_score(row)
                    new_scores.append(new_score)
                    old_score = int(row["quality_score"])
                    if new_score == old_score:
                        unchanged += 1
                        continue
                    changed.append((str(row["id"]), new_score))

                stats = (
                    {
                        "min": min(new_scores),
                        "max": max(new_scores),
                        "mean": round(statistics.fmean(new_scores), 1),
                        "median": int(statistics.median(new_scores)),
                    }
                    if new_scores
                    else {}
                )
                log.info(
                    "quality_scores_computed",
                    dry_run=dry_run,
                    scanned=len(rows),
                    updated=len(changed),
                    unchanged=unchanged,
                    where_status=status_filter or "<all>",
                    stats=stats,
                )

                if not dry_run and changed:
                    await _apply_updates(session, changed)
        finally:
            await engine.dispose()

    asyncio.run(_main())


if __name__ == "__main__":
    app()
