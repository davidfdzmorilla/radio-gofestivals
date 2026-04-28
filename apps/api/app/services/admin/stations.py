from __future__ import annotations

import math
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from fastapi import HTTPException, status as http_status
from sqlalchemy import text

from app.schemas.admin import (
    AuditEntry,
    CurationRequest,
    StationAdminDetail,
    StationGenreConfidence,
    StationListItem,
    StationListPage,
    StationPending,
    StationPendingPage,
    StationUpdate,
    StreamDetail,
    StreamRef,
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


# ---------------------------------------------------------------------------
# Tier 1 admin endpoints: list / detail / update
# ---------------------------------------------------------------------------


async def list_all(
    session: AsyncSession,
    *,
    status: str | None,
    curated: bool | None,
    search: str | None,
    page: int,
    size: int,
) -> StationListPage:
    where: list[str] = []
    params: dict[str, object] = {"limit": size, "offset": (page - 1) * size}
    if status:
        where.append("s.status = CAST(:status AS station_status)")
        params["status"] = status
    if curated is not None:
        where.append("s.curated = :curated")
        params["curated"] = curated
    if search:
        where.append("(s.name ILIKE :search OR s.slug ILIKE :search)")
        params["search"] = f"%{search}%"

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    total = (
        await session.execute(
            text(f"SELECT COUNT(*) FROM stations s {where_clause}"),  # noqa: S608
            params,
        )
    ).scalar_one()

    rows = (
        await session.execute(
            text(
                f"""
                SELECT
                    s.id, s.slug, s.name, s.status::text, s.curated,
                    s.country_code, s.quality_score, s.created_at, s.last_sync_at,
                    ss.id AS stream_id, ss.stream_url, ss.codec, ss.bitrate,
                    (SELECT COUNT(*) FROM station_streams
                       WHERE station_id = s.id) AS stream_count,
                    (SELECT COUNT(*) FROM station_genres
                       WHERE station_id = s.id) AS genre_count
                FROM stations s
                LEFT JOIN station_streams ss
                    ON ss.station_id = s.id AND ss.is_primary = true
                {where_clause}
                ORDER BY s.created_at DESC
                LIMIT :limit OFFSET :offset
                """,  # noqa: S608
            ),
            params,
        )
    ).all()

    items: list[StationListItem] = []
    for row in rows:
        primary: StreamRef | None = None
        if row[9] is not None:
            primary = StreamRef(
                id=uuid.UUID(str(row[9])),
                url=str(row[10]),
                codec=row[11],
                bitrate=row[12],
            )
        items.append(
            StationListItem(
                id=uuid.UUID(str(row[0])),
                slug=str(row[1]),
                name=str(row[2]),
                status=str(row[3]),
                curated=bool(row[4]),
                country_code=row[5],
                quality_score=int(row[6]),
                created_at=row[7],
                last_sync_at=row[8],
                primary_stream=primary,
                stream_count=int(row[13]),
                genre_count=int(row[14]),
            ),
        )

    total_int = int(total)
    return StationListPage(
        items=items,
        total=total_int,
        page=page,
        size=size,
        pages=max(1, math.ceil(total_int / size)) if total_int else 0,
    )


async def get_detail(
    session: AsyncSession, station_id: uuid.UUID,
) -> StationAdminDetail | None:
    base = (
        await session.execute(
            text(
                """
                SELECT
                    s.id, s.slug, s.name, s.status::text, s.curated,
                    s.country_code, s.city, s.language, s.homepage_url,
                    s.quality_score, s.clickcount, s.votes, s.click_trend,
                    s.failed_checks, s.last_error, s.last_check_at,
                    s.last_sync_at, s.created_at
                FROM stations s
                WHERE s.id = :id
                """,
            ),
            {"id": str(station_id)},
        )
    ).first()
    if base is None:
        return None

    stream_rows = (
        await session.execute(
            text(
                """
                SELECT id, stream_url, codec, bitrate, format, is_primary,
                       status::text, failed_checks, last_error, last_check_at
                FROM station_streams
                WHERE station_id = :id
                ORDER BY is_primary DESC, bitrate DESC NULLS LAST
                """,
            ),
            {"id": str(station_id)},
        )
    ).all()

    genre_rows = (
        await session.execute(
            text(
                """
                SELECT g.id, g.slug, g.name, sg.confidence, sg.source
                FROM station_genres sg
                JOIN genres g ON g.id = sg.genre_id
                WHERE sg.station_id = :id
                ORDER BY sg.confidence DESC, g.name ASC
                """,
            ),
            {"id": str(station_id)},
        )
    ).all()

    audit_rows = (
        await session.execute(
            text(
                """
                SELECT cl.id, a.email, cl.decision::text, cl.notes, cl.created_at
                FROM curation_log cl
                JOIN admins a ON a.id = cl.admin_id
                WHERE cl.station_id = :id
                ORDER BY cl.created_at DESC
                LIMIT 20
                """,
            ),
            {"id": str(station_id)},
        )
    ).all()

    return StationAdminDetail(
        id=uuid.UUID(str(base[0])),
        slug=str(base[1]),
        name=str(base[2]),
        status=str(base[3]),
        curated=bool(base[4]),
        country_code=base[5],
        city=base[6],
        language=base[7],
        homepage_url=base[8],
        quality_score=int(base[9]),
        clickcount=int(base[10]),
        votes=int(base[11]),
        click_trend=Decimal(str(base[12])),
        failed_checks=int(base[13]),
        last_error=base[14],
        last_check_at=base[15],
        last_sync_at=base[16],
        created_at=base[17],
        streams=[
            StreamDetail(
                id=uuid.UUID(str(r[0])),
                url=str(r[1]),
                codec=r[2],
                bitrate=r[3],
                format=r[4],
                is_primary=bool(r[5]),
                status=str(r[6]),
                failed_checks=int(r[7]),
                last_error=r[8],
                last_check_at=r[9],
            )
            for r in stream_rows
        ],
        genres=[
            StationGenreConfidence(
                genre_id=int(r[0]),
                slug=str(r[1]),
                name=str(r[2]),
                confidence=int(r[3]),
                source=str(r[4]),
            )
            for r in genre_rows
        ],
        audit=[
            AuditEntry(
                id=int(r[0]),
                admin_email=str(r[1]),
                decision=str(r[2]),
                notes=r[3],
                created_at=r[4],
            )
            for r in audit_rows
        ],
    )


async def update_station(
    session: AsyncSession,
    redis: Redis[str],
    *,
    admin_id: uuid.UUID,
    station_id: uuid.UUID,
    payload: StationUpdate,
) -> StationAdminDetail | None:
    current = (
        await session.execute(
            text(
                """
                SELECT slug, name, status::text, curated
                FROM stations WHERE id = :id
                """,
            ),
            {"id": str(station_id)},
        )
    ).first()
    if current is None:
        return None

    cur_slug, cur_name, cur_status, cur_curated = current

    if payload.slug is not None and payload.slug != cur_slug:
        clash = (
            await session.execute(
                text("SELECT 1 FROM stations WHERE slug = :s AND id <> :id"),
                {"s": payload.slug, "id": str(station_id)},
            )
        ).first()
        if clash is not None:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="slug_already_in_use",
            )

    current_genre_ids: set[int] = set()
    if payload.genre_ids is not None:
        # Validate every supplied genre id
        valid_rows = (
            await session.execute(
                text("SELECT id FROM genres WHERE id = ANY(:ids)"),
                {"ids": payload.genre_ids},
            )
        ).all()
        valid_ids = {int(r[0]) for r in valid_rows}
        invalid = [gid for gid in payload.genre_ids if gid not in valid_ids]
        if invalid:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={"error": "invalid_genre_ids", "ids": invalid},
            )
        current_genre_ids = {
            int(r[0])
            for r in (
                await session.execute(
                    text(
                        "SELECT genre_id FROM station_genres "
                        "WHERE station_id = :id",
                    ),
                    {"id": str(station_id)},
                )
            ).all()
        }

    # Build SET clause dynamically — only touch columns the caller asked for
    sets: list[str] = []
    update_params: dict[str, object] = {"id": str(station_id)}

    curated_changed = (
        payload.curated is not None and payload.curated != bool(cur_curated)
    )
    status_changed = (
        payload.status is not None and payload.status != str(cur_status)
    )
    name_changed = payload.name is not None and payload.name != cur_name
    slug_changed = payload.slug is not None and payload.slug != cur_slug
    genres_changed = (
        payload.genre_ids is not None
        and set(payload.genre_ids) != current_genre_ids
    )

    if curated_changed:
        sets.append("curated = :curated")
        update_params["curated"] = bool(payload.curated)
    if status_changed:
        sets.append("status = CAST(:status AS station_status)")
        update_params["status"] = payload.status
    if name_changed:
        sets.append("name = :name")
        update_params["name"] = payload.name
    if slug_changed:
        sets.append("slug = :slug")
        update_params["slug"] = payload.slug

    if sets:
        sets.append("updated_at = now()")
        await session.execute(
            text(
                f"UPDATE stations SET {', '.join(sets)} WHERE id = :id",  # noqa: S608
            ),
            update_params,
        )

    if genres_changed:
        await session.execute(
            text("DELETE FROM station_genres WHERE station_id = :id"),
            {"id": str(station_id)},
        )
        for gid in payload.genre_ids or []:
            await session.execute(
                text(
                    """
                    INSERT INTO station_genres (station_id, genre_id, source, confidence)
                    VALUES (:sid, :gid, 'manual', 100)
                    """,
                ),
                {"sid": str(station_id), "gid": gid},
            )

    # Audit: one curation_log entry per *kind* of change. Skip when nothing
    # changed so a no-op PATCH (e.g. curated=true → true) does not pollute
    # the audit history.
    audit_entries: list[tuple[str, str | None]] = []
    if curated_changed:
        note = (
            f"curated: {bool(cur_curated)} → {bool(payload.curated)}"
        )
        if payload.notes:
            note = f"{note}. {payload.notes}"
        audit_entries.append(("toggle_curated", note))
    if status_changed:
        note = f"status: {cur_status} → {payload.status}"
        if payload.notes:
            note = f"{note}. {payload.notes}"
        audit_entries.append(("change_status", note))
    if name_changed or slug_changed or genres_changed:
        parts: list[str] = []
        if name_changed:
            parts.append(f"name: {cur_name!r} → {payload.name!r}")
        if slug_changed:
            parts.append(f"slug: {cur_slug!r} → {payload.slug!r}")
        if genres_changed:
            parts.append(
                f"genres: {sorted(current_genre_ids)} "
                f"→ {sorted(payload.genre_ids or [])}",
            )
        note = "; ".join(parts)
        if payload.notes:
            note = f"{note}. {payload.notes}"
        audit_entries.append(("edit_metadata", note))

    for action, note in audit_entries:
        await session.execute(
            text(
                """
                INSERT INTO curation_log (admin_id, station_id, decision, notes)
                VALUES (:aid, :sid, CAST(:dec AS curation_decision), :notes)
                """,
            ),
            {
                "aid": str(admin_id),
                "sid": str(station_id),
                "dec": action,
                "notes": note,
            },
        )

    await session.commit()

    if curated_changed or status_changed or genres_changed or slug_changed:
        await invalidate_genres_cache(redis)
        keys = await _collect_station_cache_keys(redis, station_id)
        if keys:
            await redis.delete(*keys)

    return await get_detail(session, station_id)
