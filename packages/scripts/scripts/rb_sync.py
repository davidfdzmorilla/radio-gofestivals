from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import httpx
import typer
from slugify import slugify
from sqlalchemy import text

from scripts.constants import ELECTRONIC_TAGS
from scripts.db import make_engine, make_sessionmaker
from scripts.logging import get_logger
from scripts.rb_client import RadioBrowserClient
from scripts.taxonomy_mapper import GenreRef, map_rb_tags_to_genre_slugs

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


log = get_logger("rb_sync")

app = typer.Typer(help="radio.gofestivals · Radio-Browser sync")

HEALTH_CONCURRENCY = 20
HEALTH_MAX_FAILURES = 3


@dataclass
class SyncStats:
    fetched: int = 0
    deduped: int = 0
    inserted: int = 0
    updated: int = 0
    skipped_empty_url: int = 0
    skipped_hls: int = 0
    skipped_invalid: int = 0
    genre_links: int = 0
    errors: int = 0
    genre_match_hits: int = 0
    slug_collisions: int = 0
    tag_counts: dict[str, int] = field(default_factory=dict)

    def as_log_payload(self) -> dict[str, Any]:
        return {
            "fetched": self.fetched,
            "deduped": self.deduped,
            "inserted": self.inserted,
            "updated": self.updated,
            "skipped_empty_url": self.skipped_empty_url,
            "skipped_hls": self.skipped_hls,
            "skipped_invalid": self.skipped_invalid,
            "genre_links": self.genre_links,
            "genre_match_hits": self.genre_match_hits,
            "slug_collisions": self.slug_collisions,
            "errors": self.errors,
            "tag_counts": self.tag_counts,
        }


def is_valid_stream_url(url: str) -> bool:
    if not url:
        return False
    url = url.strip()
    if not url:
        return False
    return url.startswith(("http://", "https://"))


def is_hls(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".m3u8")


def normalize_country(code: str | None) -> str | None:
    if not code:
        return None
    value = code.strip().upper()[:2]
    return value or None


def parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


async def load_genres(session: AsyncSession) -> list[GenreRef]:
    result = await session.execute(text("SELECT id, slug FROM genres"))
    return [GenreRef(id=int(row[0]), slug=str(row[1])) for row in result.all()]


async def reserve_slug(session: AsyncSession, desired: str) -> tuple[str, bool]:
    """Return (final_slug, collided). Idempotente: si ya existe para rb_uuid actual,
    el caller lo reusa sin colisión añadida."""
    base = desired or "station"
    candidate = base
    suffix = 2
    while True:
        row = await session.execute(
            text("SELECT 1 FROM stations WHERE slug = :slug"),
            {"slug": candidate},
        )
        if row.first() is None:
            return candidate, candidate != base
        candidate = f"{base}-{suffix}"
        suffix += 1


async def upsert_station(
    session: AsyncSession,
    item: dict[str, Any],
    *,
    stats: SyncStats,
) -> uuid.UUID | None:
    rb_uuid_raw = item.get("stationuuid")
    if not rb_uuid_raw:
        stats.skipped_invalid += 1
        return None
    try:
        rb_uuid = uuid.UUID(str(rb_uuid_raw))
    except (ValueError, TypeError):
        stats.skipped_invalid += 1
        return None

    stream_url = (item.get("url_resolved") or item.get("url") or "").strip()
    if not is_valid_stream_url(stream_url):
        stats.skipped_empty_url += 1
        return None
    if is_hls(stream_url):
        stats.skipped_hls += 1
        return None

    name = (item.get("name") or "").strip() or "Unknown Station"
    country_code = normalize_country(item.get("countrycode"))
    city = (item.get("state") or "").strip() or None
    codec = (item.get("codec") or "").strip().lower() or None
    bitrate_raw = item.get("bitrate") or 0
    try:
        bitrate = int(bitrate_raw) or None
    except (ValueError, TypeError):
        bitrate = None
    language = (item.get("language") or "").strip().lower() or None

    def _to_float(v: Any) -> float | None:
        if v in (None, ""):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    geo_lat = _to_float(item.get("geo_lat"))
    geo_lng = _to_float(item.get("geo_long"))
    has_geo = geo_lat is not None and geo_lng is not None

    existing = await session.execute(
        text("SELECT id, slug, status FROM stations WHERE rb_uuid = :rb"),
        {"rb": str(rb_uuid)},
    )
    row = existing.first()

    if row is None:
        base_slug = slugify(name) or f"station-{rb_uuid.hex[:8]}"
        final_slug, collided = await reserve_slug(session, base_slug)
        if collided:
            stats.slug_collisions += 1
        geo_expr = (
            "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography"
            if has_geo
            else "NULL"
        )
        params: dict[str, Any] = {
            "rb": str(rb_uuid),
            "slug": final_slug,
            "name": name,
            "stream_url": stream_url,
            "country_code": country_code,
            "city": city,
            "codec": codec,
            "bitrate": bitrate,
            "language": language,
            "now": datetime.now(tz=UTC),
        }
        if has_geo:
            params["lat"] = geo_lat
            params["lng"] = geo_lng
        stmt = text(
            f"""
            INSERT INTO stations (
                rb_uuid, slug, name, stream_url, country_code, city, codec,
                bitrate, language, source, last_sync_at, geo
            ) VALUES (
                :rb, :slug, :name, :stream_url, :country_code, :city, :codec,
                :bitrate, :language, 'radio-browser', :now, {geo_expr}
            )
            RETURNING id
            """,  # noqa: S608
        )
        result = await session.execute(stmt, params)
        station_id = uuid.UUID(str(result.scalar_one()))
        stats.inserted += 1
        return station_id

    station_id = uuid.UUID(str(row[0]))
    params = {
        "id": str(station_id),
        "name": name,
        "stream_url": stream_url,
        "country_code": country_code,
        "city": city,
        "codec": codec,
        "bitrate": bitrate,
        "language": language,
        "now": datetime.now(tz=UTC),
    }
    if has_geo:
        params["lat"] = geo_lat
        params["lng"] = geo_lng
        geo_fragment = "geo = ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,"
    else:
        geo_fragment = ""
    stmt = text(
        f"""
        UPDATE stations SET
            name = :name,
            stream_url = :stream_url,
            country_code = :country_code,
            city = :city,
            codec = :codec,
            bitrate = :bitrate,
            language = :language,
            {geo_fragment}
            last_sync_at = :now
        WHERE id = :id
        """,  # noqa: S608
    )
    await session.execute(stmt, params)
    stats.updated += 1
    return station_id


async def replace_rb_tag_links(
    session: AsyncSession,
    station_id: uuid.UUID,
    matches: list[tuple[int, int]],
    *,
    stats: SyncStats,
) -> None:
    await session.execute(
        text(
            "DELETE FROM station_genres WHERE station_id = :sid AND source = 'rb_tag'",
        ),
        {"sid": str(station_id)},
    )
    for genre_id, confidence in matches:
        await session.execute(
            text(
                """
                INSERT INTO station_genres (station_id, genre_id, source, confidence)
                VALUES (:sid, :gid, 'rb_tag', :conf)
                ON CONFLICT (station_id, genre_id) DO NOTHING
                """,
            ),
            {"sid": str(station_id), "gid": genre_id, "conf": confidence},
        )
        stats.genre_links += 1


async def sync_tag(
    session: AsyncSession,
    client: RadioBrowserClient,
    tag: str,
    limit: int,
    *,
    seen: set[str],
    genres: list[GenreRef],
    stats: SyncStats,
) -> None:
    items = await client.fetch_stations_by_tag(tag, limit=limit)
    stats.fetched += len(items)
    stats.tag_counts[tag] = len(items)

    for item in items:
        rb_uuid = str(item.get("stationuuid") or "")
        if not rb_uuid or rb_uuid in seen:
            stats.deduped += 1
            continue
        seen.add(rb_uuid)

        try:
            station_id = await upsert_station(session, item, stats=stats)
        except Exception:
            stats.errors += 1
            log.exception("upsert_failed", rb_uuid=rb_uuid)
            continue
        if station_id is None:
            continue

        tags = parse_tags(item.get("tags"))
        matches = map_rb_tags_to_genre_slugs(tags, genres)
        if matches:
            stats.genre_match_hits += 1
        await replace_rb_tag_links(session, station_id, matches, stats=stats)


async def run_sync(
    maker: async_sessionmaker[AsyncSession],
    *,
    tag: str | None,
    dry_run: bool,
    limit: int,
    client: RadioBrowserClient | None = None,
) -> SyncStats:
    stats = SyncStats()
    tags = [tag] if tag else ELECTRONIC_TAGS
    seen: set[str] = set()

    rb = client or RadioBrowserClient()

    async with rb, maker() as session:
        genres = await load_genres(session)
        log.info("sync_start", dry_run=dry_run, tags=tags, genres_loaded=len(genres))

        for t in tags:
            try:
                await sync_tag(
                    session, rb, t, limit=limit, seen=seen, genres=genres, stats=stats,
                )
            except Exception:
                stats.errors += 1
                log.exception("tag_fetch_failed", tag=t)

        if dry_run:
            await session.rollback()
            log.info("sync_done_dry_run", **stats.as_log_payload())
        else:
            await session.commit()
            log.info("sync_done", **stats.as_log_payload())
    return stats


@app.command("run")
def cmd_run(
    tag: str | None = typer.Option(None, "--tag", help="Un solo tag en lugar de toda la whitelist"),
    dry_run: bool = typer.Option(False, "--dry-run", help="No commitea cambios"),  # noqa: FBT001,FBT002
    limit: int = typer.Option(
        int(os.environ.get("RB_SYNC_TAG_LIMIT", "500")),
        "--limit",
        help="Límite por tag",
    ),
) -> None:
    engine = make_engine()
    maker = make_sessionmaker(engine)

    async def _main() -> SyncStats:
        try:
            return await run_sync(maker, tag=tag, dry_run=dry_run, limit=limit)
        finally:
            await engine.dispose()

    asyncio.run(_main())


async def check_station_head(
    client: httpx.AsyncClient,
    url: str,
    timeout: float,
) -> bool:
    try:
        resp = await client.head(url, timeout=timeout, follow_redirects=True)
    except (httpx.TimeoutException, httpx.TransportError):
        return False
    return resp.status_code < httpx.codes.BAD_REQUEST


async def _iter_health_candidates(
    session: AsyncSession,
) -> AsyncIterator[tuple[uuid.UUID, str, int, str]]:
    result = await session.execute(
        text(
            """
            SELECT id, stream_url, failed_checks, status
            FROM stations
            WHERE status IN ('active', 'broken')
            ORDER BY last_check_ok NULLS FIRST
            """,
        ),
    )
    for row in result.all():
        yield uuid.UUID(str(row[0])), str(row[1]), int(row[2]), str(row[3])


async def run_health_check(
    maker: async_sessionmaker[AsyncSession],
    *,
    timeout: float = 5.0,
    client: httpx.AsyncClient | None = None,
) -> dict[str, int]:
    stats = {"checked": 0, "ok": 0, "failed": 0, "marked_broken": 0, "recovered": 0}
    close_client = client is None
    hc = client or httpx.AsyncClient()
    sem = asyncio.Semaphore(HEALTH_CONCURRENCY)

    async with maker() as session:
        candidates = [c async for c in _iter_health_candidates(session)]

        async def _one(station_id: uuid.UUID, url: str, failed: int, prev: str) -> None:
            async with sem:
                ok = await check_station_head(hc, url, timeout)
            if ok:
                new_status = "active" if prev == "broken" else prev
                await session.execute(
                    text(
                        """
                        UPDATE stations SET failed_checks = 0,
                                            last_check_ok = now(),
                                            status = :st
                        WHERE id = :id
                        """,
                    ),
                    {"id": str(station_id), "st": new_status},
                )
                stats["ok"] += 1
                if prev == "broken" and new_status == "active":
                    stats["recovered"] += 1
            else:
                new_failed = failed + 1
                new_status = "broken" if new_failed >= HEALTH_MAX_FAILURES else prev
                await session.execute(
                    text(
                        """
                        UPDATE stations SET failed_checks = :fc, status = :st
                        WHERE id = :id
                        """,
                    ),
                    {"id": str(station_id), "fc": new_failed, "st": new_status},
                )
                stats["failed"] += 1
                if new_status == "broken" and prev != "broken":
                    stats["marked_broken"] += 1
            stats["checked"] += 1

        await asyncio.gather(*(_one(*c) for c in candidates))
        await session.commit()

    if close_client:
        await hc.aclose()
    log.info("health_check_done", **stats)
    return stats


@app.command("health-check")
def cmd_health_check(timeout: float = typer.Option(5.0, "--timeout")) -> None:
    engine = make_engine()
    maker = make_sessionmaker(engine)

    async def _main() -> None:
        try:
            await run_health_check(maker, timeout=timeout)
        finally:
            await engine.dispose()

    asyncio.run(_main())


async def collect_stats(session: AsyncSession) -> dict[str, Any]:
    by_status = {
        str(r[0]): int(r[1])
        for r in (
            await session.execute(
                text("SELECT status, COUNT(*) FROM stations GROUP BY status"),
            )
        ).all()
    }
    by_country = {
        str(r[0] or "??"): int(r[1])
        for r in (
            await session.execute(
                text(
                    """
                    SELECT country_code, COUNT(*) FROM stations
                    WHERE status = 'active'
                    GROUP BY country_code ORDER BY 2 DESC LIMIT 10
                    """,
                ),
            )
        ).all()
    }
    by_genre = {
        str(r[0]): int(r[1])
        for r in (
            await session.execute(
                text(
                    """
                    SELECT g.slug, COUNT(DISTINCT sg.station_id)
                    FROM genres g
                    LEFT JOIN station_genres sg ON sg.genre_id = g.id
                    LEFT JOIN stations s ON s.id = sg.station_id AND s.status = 'active'
                    GROUP BY g.slug ORDER BY 2 DESC
                    """,
                ),
            )
        ).all()
    }
    return {"by_status": by_status, "top_countries": by_country, "by_genre": by_genre}


@app.command("show-stats")
def cmd_show_stats() -> None:
    engine = make_engine()
    maker = make_sessionmaker(engine)

    async def _main() -> None:
        try:
            async with maker() as session:
                data = await collect_stats(session)
            log.info("stats", **data)
        finally:
            await engine.dispose()

    asyncio.run(_main())


AUTO_CURATE_MAX_LIMIT = 200


@dataclass
class AutoCurateStats:
    curated: int = 0
    skipped_already_curated: int = 0
    skipped_below_quality: int = 0


async def _resolve_active_admin(session: AsyncSession, email: str) -> uuid.UUID | None:
    row = (
        await session.execute(
            text("SELECT id, active FROM admins WHERE lower(email) = lower(:e)"),
            {"e": email},
        )
    ).first()
    if row is None or not row[1]:
        return None
    return uuid.UUID(str(row[0]))


async def run_auto_curate_top(
    maker: async_sessionmaker[AsyncSession],
    *,
    admin_email: str,
    limit: int,
    country: str | None,
    min_quality: int,
    dry_run: bool,
) -> AutoCurateStats:
    if limit > AUTO_CURATE_MAX_LIMIT:
        msg = f"--limit {limit} exceeds max {AUTO_CURATE_MAX_LIMIT}"
        raise ValueError(msg)

    stats = AutoCurateStats()

    async with maker() as session:
        admin_id = await _resolve_active_admin(session, admin_email)
        if admin_id is None:
            msg = f"admin not found or inactive: {admin_email}"
            raise ValueError(msg)

        below_params: dict[str, object] = {"min_q": min_quality}
        below_where = ["status = 'pending'", "quality_score < :min_q"]
        if country:
            below_where.append("country_code = :country")
            below_params["country"] = country.upper()
        stats.skipped_below_quality = int(
            (
                await session.execute(
                    text(
                        f"SELECT COUNT(*) FROM stations WHERE {' AND '.join(below_where)}",  # noqa: S608
                    ),
                    below_params,
                )
            ).scalar_one(),
        )

        select_params: dict[str, object] = {"min_q": min_quality, "limit": limit}
        select_where = ["status = 'pending'", "quality_score >= :min_q"]
        if country:
            select_where.append("country_code = :country")
            select_params["country"] = country.upper()
        candidate_rows = (
            await session.execute(
                text(
                    f"""
                    SELECT id FROM stations
                    WHERE {" AND ".join(select_where)}
                    ORDER BY quality_score DESC, created_at ASC
                    LIMIT :limit
                    """,  # noqa: S608
                ),
                select_params,
            )
        ).all()
        candidate_ids = [uuid.UUID(str(r[0])) for r in candidate_rows]

        for station_id in candidate_ids:
            await session.execute(
                text(
                    """
                    UPDATE stations
                    SET curated = true, status = 'active'
                    WHERE id = :id
                    """,
                ),
                {"id": str(station_id)},
            )
            await session.execute(
                text(
                    """
                    INSERT INTO curation_log (admin_id, station_id, decision, notes)
                    VALUES (:aid, :sid, CAST('approve' AS curation_decision), :notes)
                    """,
                ),
                {
                    "aid": str(admin_id),
                    "sid": str(station_id),
                    "notes": "auto-curate-top",
                },
            )
            stats.curated += 1

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    log.info(
        "auto_curate_done",
        curated=stats.curated,
        skipped_already_curated=stats.skipped_already_curated,
        skipped_below_quality=stats.skipped_below_quality,
        admin_email=admin_email,
        country=country,
        min_quality=min_quality,
        limit=limit,
        dry_run=dry_run,
    )
    return stats


@app.command("auto-curate-top")
def cmd_auto_curate_top(
    limit: int = typer.Option(50, "--limit", max=AUTO_CURATE_MAX_LIMIT),
    country: str | None = typer.Option(None, "--country"),
    min_quality: int = typer.Option(60, "--min-quality", min=0, max=100),
    dry_run: bool = typer.Option(False, "--dry-run"),
    admin_email: str = typer.Option(..., "--admin-email"),
) -> None:
    engine = make_engine()
    maker = make_sessionmaker(engine)

    async def _main() -> None:
        try:
            await run_auto_curate_top(
                maker,
                admin_email=admin_email,
                limit=limit,
                country=country,
                min_quality=min_quality,
                dry_run=dry_run,
            )
        finally:
            await engine.dispose()

    try:
        asyncio.run(_main())
    except ValueError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
