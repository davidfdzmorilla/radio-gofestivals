"""Conservative dedupe of stations imported from Radio-Browser.

Radio-Browser exposes the same logical station several times with
different bitrate/codec/UUID combinations. Until we model that properly
(stations + station_streams split), this script marks redundant rows
as `status='duplicate'` so public endpoints (which already filter
`status='active'`) hide them.

Two stations are considered duplicates when ALL of:
  - normalized name matches
  - country_code matches
  - homepage_url matches, treating NULL as equal-to-anything

The "winner" of each group is picked deterministically by:
  1. higher bitrate
  2. preferred codec (opus > aac+ > aac > mp3 > other)
  3. higher quality_score (proxy for Radio-Browser clickcount)
  4. older created_at (first to land in our DB)
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

import typer
from sqlalchemy import text

from scripts.db import make_engine, make_sessionmaker
from scripts.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession


log = get_logger("dedupe_stations")
app = typer.Typer(help="radio.gofestivals · mark Radio-Browser duplicates")


# Higher rank wins. Unknown codecs get 1 (still better than NULL=0).
_CODEC_RANK: dict[str, int] = {
    "opus": 5,
    "aac+": 4,
    "aacp": 4,
    "aac": 3,
    "mp3": 2,
}


def normalize_name(name: str) -> str:
    """Lowercase, strip leading punctuation/whitespace, collapse spaces."""
    s = name.lower().strip()
    while s and s[0] in "-—–_•· \t":
        s = s[1:].lstrip()
    return " ".join(s.split())


def codec_rank(codec: str | None) -> int:
    if codec is None:
        return 0
    return _CODEC_RANK.get(codec.lower().strip(), 1)


@dataclass(frozen=True)
class StationRow:
    id: str
    name: str
    country_code: str | None
    homepage_url: str | None
    bitrate: int | None
    codec: str | None
    quality_score: int
    created_at: "datetime"
    status: str


def dedupe_key(row: StationRow) -> tuple[str, str, str]:
    """Return a tuple identifying the dedupe group.

    Stations with NULL homepage_url collapse onto the empty string, so they
    group with any other entry sharing the same (name, country) — the
    conservative interpretation requested by the spec ("if one has homepage
    NULL, consider equal").
    """
    return (
        normalize_name(row.name),
        (row.country_code or "").upper(),
        (row.homepage_url or "").strip().lower(),
    )


def pick_best(rows: list[StationRow]) -> StationRow:
    """Pick the survivor of a duplicate group by the spec's tie-breakers."""
    return max(
        rows,
        key=lambda r: (
            r.bitrate or 0,
            codec_rank(r.codec),
            r.quality_score,
            -r.created_at.timestamp(),
        ),
    )


def group_by_key(rows: Iterable[StationRow]) -> dict[tuple[str, str, str], list[StationRow]]:
    groups: dict[tuple[str, str, str], list[StationRow]] = {}
    for r in rows:
        groups.setdefault(dedupe_key(r), []).append(r)
    return groups


@dataclass
class DedupeStats:
    rows_scanned: int = 0
    groups_total: int = 0
    groups_with_duplicates: int = 0
    marked_duplicate: int = 0
    kept: int = 0


async def _fetch_candidates(session: AsyncSession) -> list[StationRow]:
    result = await session.execute(
        text(
            """
            SELECT id::text, name, country_code, homepage_url,
                   bitrate, codec, quality_score, created_at, status
            FROM stations
            WHERE status != 'duplicate'
            """,
        ),
    )
    return [
        StationRow(
            id=row[0],
            name=row[1],
            country_code=row[2],
            homepage_url=row[3],
            bitrate=row[4],
            codec=row[5],
            quality_score=row[6],
            created_at=row[7],
            status=row[8],
        )
        for row in result.all()
    ]


async def _mark_duplicates(session: AsyncSession, ids: list[str]) -> None:
    if not ids:
        return
    await session.execute(
        text("UPDATE stations SET status = 'duplicate' WHERE id = ANY(CAST(:ids AS uuid[]))"),
        {"ids": ids},
    )


async def dedupe_run(session: AsyncSession, *, dry_run: bool) -> DedupeStats:
    rows = await _fetch_candidates(session)
    groups = group_by_key(rows)

    stats = DedupeStats(rows_scanned=len(rows), groups_total=len(groups))
    losers: list[str] = []

    for key, group in groups.items():
        if len(group) <= 1:
            stats.kept += 1
            continue
        stats.groups_with_duplicates += 1
        winner = pick_best(group)
        stats.kept += 1
        for r in group:
            if r.id == winner.id:
                continue
            losers.append(r.id)
            log.info(
                "marking_duplicate",
                loser_id=r.id,
                winner_id=winner.id,
                name=r.name,
                country_code=r.country_code,
                key=key,
                dry_run=dry_run,
            )

    stats.marked_duplicate = len(losers)

    if not dry_run:
        await _mark_duplicates(session, losers)
        await session.commit()

    return stats


@app.command("run")
def cmd_run(
    dry_run: bool = typer.Option(
        default=True,
        help="If true, log what would change without writing.",
        rich_help_panel="Mode",
    ),
    apply: bool = typer.Option(
        default=False,
        help="Apply the dedupe (overrides --dry-run).",
        rich_help_panel="Mode",
    ),
) -> None:
    """Mark Radio-Browser duplicates as status='duplicate'."""
    effective_dry_run = dry_run and not apply

    async def _main() -> None:
        engine = make_engine()
        maker = make_sessionmaker(engine)
        try:
            async with maker() as session:
                stats = await dedupe_run(session, dry_run=effective_dry_run)
            log.info(
                "dedupe_complete",
                dry_run=effective_dry_run,
                rows_scanned=stats.rows_scanned,
                groups_total=stats.groups_total,
                groups_with_duplicates=stats.groups_with_duplicates,
                marked_duplicate=stats.marked_duplicate,
                kept=stats.kept,
            )
        finally:
            await engine.dispose()

    asyncio.run(_main())


if __name__ == "__main__":
    app()
