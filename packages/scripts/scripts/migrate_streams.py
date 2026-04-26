"""migrate-streams · backfill station_streams from legacy stations columns.

For each station with stream_url, attach a station_stream row to the
brand owner of its dedupe group. Brand owner is determined by the same
key used elsewhere: (normalized_name, country_code, homepage_url, with
NULL homepage matching anything in the same name+country bucket).

Per group:
  - If exactly one row exists, it stays as the brand and gets one stream.
  - If multiple exist, the one with status='active' becomes the brand;
    others (already marked status='duplicate' by an earlier dedupe) are
    flipped to status='inactive' (preserve history, no DELETE) and their
    stream attaches to the brand owner.
  - If no row in the group is 'active' (only duplicates) the highest-
    technical-score row is promoted to 'active' and becomes the brand.

After all streams exist, exactly one per station is marked is_primary=true,
chosen by technical_score (highest bitrate × codec factor).
"""
from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import typer
from sqlalchemy import text

from scripts.db import make_engine, make_sessionmaker
from scripts.dedupe_stations import dedupe_key as _dedupe_key_for_row
from scripts.logging import get_logger
from scripts.quality import compute_technical_score

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


log = get_logger("migrate_streams")
app = typer.Typer(help="radio.gofestivals · backfill station_streams")


@dataclass(frozen=True)
class _Row:
    id: str
    name: str
    country_code: str | None
    homepage_url: str | None
    stream_url: str
    codec: str | None
    bitrate: int | None
    status: str


@dataclass
class MigrationStats:
    stations_kept_as_brand: int = 0
    stations_marked_inactive_after_merge: int = 0
    stations_promoted_from_duplicate: int = 0
    streams_created: int = 0
    primary_streams_assigned: int = 0
    skipped_no_stream_url: int = 0
    errors: list[str] = field(default_factory=list)


def _row_key(r: _Row) -> tuple[str, str, str]:
    # Reuse dedupe_stations.dedupe_key by adapting the StationRow shape.
    class _Adapter:
        name = r.name
        country_code = r.country_code
        homepage_url = r.homepage_url

    return _dedupe_key_for_row(_Adapter)  # type: ignore[arg-type]


async def _fetch_all(session: AsyncSession) -> list[_Row]:
    result = await session.execute(
        text(
            """
            SELECT id::text, name, country_code, homepage_url, stream_url,
                   codec, bitrate, status
            FROM stations
            WHERE stream_url IS NOT NULL
            """,
        ),
    )
    return [
        _Row(
            id=row[0], name=row[1], country_code=row[2], homepage_url=row[3],
            stream_url=row[4], codec=row[5], bitrate=row[6], status=row[7],
        )
        for row in result.all()
    ]


def _pick_brand(group: list[_Row]) -> tuple[_Row, list[_Row], bool]:
    """Return (brand, others, promoted_from_duplicate).

    Brand selection by status priority: active > pending > broken > duplicate.
    Within the top tier, highest technical_score wins. `promoted_from_duplicate`
    is only true when the brand we picked currently has status='duplicate'
    AND there's no active/pending in the group — i.e. the group is rescued
    from being entirely shadow rows.

    Pending brands stay pending; we never auto-promote pending → active here.
    """
    by_status: dict[str, list[_Row]] = {}
    for r in group:
        by_status.setdefault(r.status, []).append(r)

    for tier in ("active", "pending", "broken", "duplicate"):
        bucket = by_status.get(tier)
        if not bucket:
            continue
        bucket.sort(
            key=lambda r: compute_technical_score(r.bitrate, r.codec),
            reverse=True,
        )
        brand = bucket[0]
        others = [r for r in group if r.id != brand.id]
        promoted = tier == "duplicate"
        return brand, others, promoted

    # group was empty in practice; defensive
    raise ValueError("empty group")


async def _create_stream(
    session: AsyncSession,
    *,
    station_id: str,
    stream_url: str,
    codec: str | None,
    bitrate: int | None,
) -> bool:
    """Insert one stream. Returns True if a new row was created (idempotent)."""
    result = await session.execute(
        text(
            """
            INSERT INTO station_streams
                (station_id, stream_url, codec, bitrate, format, status)
            VALUES
                (CAST(:sid AS uuid), :url, :codec, :br, :codec, 'active')
            ON CONFLICT (station_id, stream_url) DO NOTHING
            RETURNING id
            """,
        ),
        {"sid": station_id, "url": stream_url, "codec": codec, "br": bitrate},
    )
    return result.first() is not None


async def _assign_primaries(session: AsyncSession) -> int:
    """For each station, set is_primary=true on the highest-technical stream.

    Returns number of stations whose primary was (re)assigned.
    """
    rows = (
        await session.execute(
            text(
                """
                SELECT id::text, station_id::text, codec, bitrate
                FROM station_streams
                """,
            ),
        )
    ).all()
    by_station: dict[str, list[tuple[str, str | None, int | None]]] = defaultdict(list)
    for r in rows:
        by_station[r[1]].append((r[0], r[2], r[3]))

    winners: list[str] = []
    for streams in by_station.values():
        streams.sort(
            key=lambda s: compute_technical_score(s[2], s[1]),
            reverse=True,
        )
        winners.append(streams[0][0])

    if not winners:
        return 0
    # Reset all primaries first, then mark winners — single transaction.
    await session.execute(
        text(
            "UPDATE station_streams SET is_primary = false WHERE is_primary = true",
        ),
    )
    await session.execute(
        text(
            "UPDATE station_streams SET is_primary = true "
            "WHERE id = ANY(CAST(:ids AS uuid[]))",
        ),
        {"ids": winners},
    )
    return len(winners)


async def _mark_inactive(session: AsyncSession, ids: list[str]) -> None:
    if not ids:
        return
    await session.execute(
        text(
            "UPDATE stations SET status = 'inactive' "
            "WHERE id = ANY(CAST(:ids AS uuid[]))",
        ),
        {"ids": ids},
    )


async def _promote_to_active(session: AsyncSession, ids: list[str]) -> None:
    if not ids:
        return
    await session.execute(
        text(
            "UPDATE stations SET status = 'active' "
            "WHERE id = ANY(CAST(:ids AS uuid[]))",
        ),
        {"ids": ids},
    )


async def migrate_run(session: AsyncSession, *, dry_run: bool) -> MigrationStats:
    rows = await _fetch_all(session)
    groups: dict[tuple[str, str, str], list[_Row]] = defaultdict(list)
    for r in rows:
        groups[_row_key(r)].append(r)

    stats = MigrationStats()
    inactive_ids: list[str] = []
    promote_ids: list[str] = []
    streams_to_create: list[tuple[str, _Row]] = []

    for group in groups.values():
        brand, others, promoted = _pick_brand(group)
        if promoted:
            promote_ids.append(brand.id)
            stats.stations_promoted_from_duplicate += 1
        stats.stations_kept_as_brand += 1
        # Brand's own stream
        streams_to_create.append((brand.id, brand))
        # Other rows' streams attach to the brand's id
        for o in others:
            streams_to_create.append((brand.id, o))
            inactive_ids.append(o.id)
            stats.stations_marked_inactive_after_merge += 1

    if dry_run:
        # Approximate created count; uniqueness skipped because INSERT is the
        # gate for that — count distinct (brand_id, stream_url) pairs.
        unique_pairs = {(bid, r.stream_url) for bid, r in streams_to_create}
        stats.streams_created = len(unique_pairs)
        stats.primary_streams_assigned = stats.stations_kept_as_brand
        return stats

    await _promote_to_active(session, promote_ids)

    for brand_id, src in streams_to_create:
        try:
            created = await _create_stream(
                session,
                station_id=brand_id,
                stream_url=src.stream_url,
                codec=src.codec,
                bitrate=src.bitrate,
            )
            if created:
                stats.streams_created += 1
        except Exception as exc:  # noqa: BLE001
            stats.errors.append(f"{brand_id}: {exc!s}")

    await _mark_inactive(session, inactive_ids)
    stats.primary_streams_assigned = await _assign_primaries(session)
    await session.commit()
    return stats


@app.command()
def migrate_streams(
    dry_run: bool = typer.Option(default=True, help="Log what would change."),
    apply: bool = typer.Option(default=False, help="Apply (overrides --dry-run)."),
) -> None:
    """Backfill station_streams from legacy stations columns."""
    effective_dry_run = dry_run and not apply

    async def _main() -> None:
        engine = make_engine()
        maker = make_sessionmaker(engine)
        try:
            async with maker() as session:
                stats = await migrate_run(session, dry_run=effective_dry_run)
            log.info(
                "migrate_streams_done",
                dry_run=effective_dry_run,
                stations_kept_as_brand=stats.stations_kept_as_brand,
                stations_marked_inactive_after_merge=(
                    stats.stations_marked_inactive_after_merge
                ),
                stations_promoted_from_duplicate=(
                    stats.stations_promoted_from_duplicate
                ),
                streams_created=stats.streams_created,
                primary_streams_assigned=stats.primary_streams_assigned,
                errors=stats.errors[:10],
                error_count=len(stats.errors),
            )
        finally:
            await engine.dispose()

    asyncio.run(_main())


if __name__ == "__main__":
    app()
