from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def list_favorites(
    session: AsyncSession, user_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Return favorites joined with station summary fields.

    Uses a single query with LEFT JOIN to station_streams for the primary
    so the response can render a play button without an N+1.
    """
    rows = (
        await session.execute(
            text(
                """
                SELECT
                    uf.station_id,
                    uf.created_at,
                    s.slug, s.name, s.country_code, s.city, s.curated,
                    s.quality_score, s.status::text AS status,
                    ss.id AS stream_id, ss.stream_url, ss.codec, ss.bitrate,
                    ss.format
                FROM user_favorites uf
                JOIN stations s ON s.id = uf.station_id
                LEFT JOIN station_streams ss
                    ON ss.station_id = s.id AND ss.is_primary = true
                WHERE uf.user_id = :uid
                ORDER BY uf.created_at DESC
                """,
            ),
            {"uid": str(user_id)},
        )
    ).all()
    return [
        {
            "station_id": uuid.UUID(str(r[0])),
            "created_at": r[1],
            "slug": str(r[2]),
            "name": str(r[3]),
            "country_code": r[4],
            "city": r[5],
            "curated": bool(r[6]),
            "quality_score": int(r[7]),
            "status": str(r[8]),
            "primary_stream": (
                {
                    "id": uuid.UUID(str(r[9])),
                    "url": str(r[10]),
                    "codec": r[11],
                    "bitrate": r[12],
                    "format": r[13],
                }
                if r[9] is not None
                else None
            ),
        }
        for r in rows
    ]


async def add_favorite(
    session: AsyncSession,
    user_id: uuid.UUID,
    station_id: uuid.UUID,
) -> bool:
    """Idempotent insert. Returns True if newly added, False if already there."""
    result = await session.execute(
        text(
            """
            INSERT INTO user_favorites (user_id, station_id)
            VALUES (:uid, :sid)
            ON CONFLICT (user_id, station_id) DO NOTHING
            RETURNING user_id
            """,
        ),
        {"uid": str(user_id), "sid": str(station_id)},
    )
    return result.first() is not None


async def remove_favorite(
    session: AsyncSession,
    user_id: uuid.UUID,
    station_id: uuid.UUID,
) -> bool:
    result = await session.execute(
        text(
            """
            DELETE FROM user_favorites
            WHERE user_id = :uid AND station_id = :sid
            RETURNING user_id
            """,
        ),
        {"uid": str(user_id), "sid": str(station_id)},
    )
    return result.first() is not None


async def bulk_add_favorites(
    session: AsyncSession,
    user_id: uuid.UUID,
    station_ids: list[uuid.UUID],
) -> dict[str, int]:
    """Bulk upsert. Skips ids that don't reference a real station.

    Returns counts: added (newly inserted), already_existed (skipped on
    conflict), invalid (station_id not found in stations).
    """
    if not station_ids:
        return {"added": 0, "already_existed": 0, "invalid": 0}

    ids_str = [str(s) for s in station_ids]
    valid_rows = (
        await session.execute(
            text(
                "SELECT id FROM stations WHERE id = ANY(CAST(:ids AS uuid[]))",
            ),
            {"ids": ids_str},
        )
    ).all()
    valid_ids = {str(r[0]) for r in valid_rows}
    invalid = len(set(ids_str)) - len(valid_ids)

    if not valid_ids:
        return {"added": 0, "already_existed": 0, "invalid": invalid}

    inserted = (
        await session.execute(
            text(
                """
                INSERT INTO user_favorites (user_id, station_id)
                SELECT :uid, sid FROM unnest(CAST(:ids AS uuid[])) AS sid
                ON CONFLICT (user_id, station_id) DO NOTHING
                RETURNING station_id
                """,
            ),
            {"uid": str(user_id), "ids": list(valid_ids)},
        )
    ).all()
    added = len(inserted)
    return {
        "added": added,
        "already_existed": len(valid_ids) - added,
        "invalid": invalid,
    }


async def get_favorite_station_ids(
    session: AsyncSession,
    user_id: uuid.UUID,
    station_ids: list[uuid.UUID],
) -> set[uuid.UUID]:
    """For a given list of station ids, return which ones the user favorited."""
    if not station_ids:
        return set()
    rows = (
        await session.execute(
            text(
                """
                SELECT station_id FROM user_favorites
                WHERE user_id = :uid
                  AND station_id = ANY(CAST(:ids AS uuid[]))
                """,
            ),
            {
                "uid": str(user_id),
                "ids": [str(s) for s in station_ids],
            },
        )
    ).all()
    return {uuid.UUID(str(r[0])) for r in rows}
