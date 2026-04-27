from __future__ import annotations

import math
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import text

from app.schemas.admin import (
    CurationRequest,
    StationGenreConfidence,
    StationPending,
    StationPendingPage,
)
from app.services.genres import invalidate_genres_cache

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession


async def list_pending(
    session: AsyncSession,
    *,
    country: str | None,
    has_geo: bool | None,
    min_quality: int | None,
    page: int,
    size: int,
) -> StationPendingPage:
    where = ["s.status = 'pending'"]
    params: dict[str, object] = {"limit": size, "offset": (page - 1) * size}
    if country:
        where.append("s.country_code = :country")
        params["country"] = country.upper()
    if has_geo is True:
        where.append("s.geo IS NOT NULL")
    elif has_geo is False:
        where.append("s.geo IS NULL")
    if min_quality is not None:
        where.append("s.quality_score >= :min_q")
        params["min_q"] = min_quality

    where_clause = " AND ".join(where)

    total = (
        await session.execute(
            text(f"SELECT COUNT(*) FROM stations s WHERE {where_clause}"),  # noqa: S608
            params,
        )
    ).scalar_one()

    # stream_url/codec/bitrate moved to station_streams in migration 0007.
    # LEFT JOIN the primary stream so admin pending lists keep showing the
    # technical info that operators rely on for curation decisions.
    rows = (
        await session.execute(
            text(
                f"""
                SELECT s.id, s.slug, s.name, ss.stream_url, s.country_code, s.city,
                       ss.codec, ss.bitrate, s.quality_score, s.created_at,
                       s.last_sync_at, s.geo IS NOT NULL AS has_geo
                FROM stations s
                LEFT JOIN station_streams ss
                  ON ss.station_id = s.id AND ss.is_primary = true
                WHERE {where_clause}
                ORDER BY s.quality_score DESC, s.created_at ASC
                LIMIT :limit OFFSET :offset
                """,  # noqa: S608
            ),
            params,
        )
    ).all()

    station_ids = [row[0] for row in rows]
    genres_by_station: dict[uuid.UUID, list[StationGenreConfidence]] = {}
    if station_ids:
        genre_rows = (
            await session.execute(
                text(
                    """
                    SELECT sg.station_id, g.id, g.slug, g.name, sg.confidence, sg.source
                    FROM station_genres sg
                    JOIN genres g ON g.id = sg.genre_id
                    WHERE sg.station_id = ANY(:ids)
                    ORDER BY sg.confidence DESC
                    """,
                ),
                {"ids": station_ids},
            )
        ).all()
        for gr in genre_rows:
            sid = uuid.UUID(str(gr[0]))
            genres_by_station.setdefault(sid, []).append(
                StationGenreConfidence(
                    genre_id=int(gr[1]),
                    slug=str(gr[2]),
                    name=str(gr[3]),
                    confidence=int(gr[4]),
                    source=str(gr[5]),
                ),
            )

    items = [
        StationPending(
            id=uuid.UUID(str(row[0])),
            slug=str(row[1]),
            name=str(row[2]),
            stream_url=row[3],
            country_code=row[4],
            city=row[5],
            codec=row[6],
            bitrate=row[7],
            quality_score=int(row[8]),
            created_at=row[9],
            last_sync_at=row[10],
            has_geo=bool(row[11]),
            genres=genres_by_station.get(uuid.UUID(str(row[0])), []),
        )
        for row in rows
    ]

    return StationPendingPage(
        items=items,
        total=int(total),
        page=page,
        size=size,
        pages=max(1, math.ceil(int(total) / size)) if total else 0,
    )


async def apply_curation(
    session: AsyncSession,
    redis: Redis[str],
    *,
    admin_id: uuid.UUID,
    station_id: uuid.UUID,
    decision: CurationRequest,
) -> tuple[str, bool, int] | None:
    existing = (
        await session.execute(
            text("SELECT id FROM stations WHERE id = :id"),
            {"id": str(station_id)},
        )
    ).first()
    if existing is None:
        return None

    if decision.decision == "reject":
        new_status, curated = "rejected", False
    else:
        new_status, curated = "active", True

    update_params: dict[str, object] = {
        "id": str(station_id),
        "status": new_status,
        "curated": curated,
    }
    quality_fragment = ""
    if decision.quality_score is not None:
        quality_fragment = ", quality_score = :qs"
        update_params["qs"] = decision.quality_score
    await session.execute(
        text(
            f"""
            UPDATE stations SET
                status = CAST(:status AS station_status),
                curated = :curated
                {quality_fragment}
            WHERE id = :id
            """,  # noqa: S608
        ),
        update_params,
    )

    if decision.decision == "reclassify":
        await session.execute(
            text("DELETE FROM station_genres WHERE station_id = :id"),
            {"id": str(station_id)},
        )
        for gid in decision.genre_ids:
            await session.execute(
                text(
                    """
                    INSERT INTO station_genres (station_id, genre_id, source, confidence)
                    VALUES (:sid, :gid, 'manual', 100)
                    """,
                ),
                {"sid": str(station_id), "gid": gid},
            )

    log_id = (
        await session.execute(
            text(
                """
                INSERT INTO curation_log (admin_id, station_id, decision, notes)
                VALUES (:aid, :sid, CAST(:dec AS curation_decision), :notes)
                RETURNING id
                """,
            ),
            {
                "aid": str(admin_id),
                "sid": str(station_id),
                "dec": decision.decision,
                "notes": decision.notes,
            },
        )
    ).scalar_one()

    await session.commit()
    await invalidate_genres_cache(redis)
    await redis.delete(*await _collect_station_cache_keys(redis, station_id))
    return new_status, curated, int(log_id)


async def _collect_station_cache_keys(
    redis: Redis[str], station_id: uuid.UUID,
) -> list[str]:
    # slug-based detail key isn't known; best-effort scan over station:detail:*
    keys: list[str] = []
    async for key in redis.scan_iter("station:detail:*"):
        keys.append(key)
    if not keys:
        keys = [f"station:detail:_noop:{station_id}"]
    return keys
