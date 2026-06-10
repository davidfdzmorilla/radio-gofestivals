"""Acceso a datos del sistema de recomendación (docs/recommendations-plan.md).

Lecturas on-the-fly del request path: semillas de la identidad, vecinos
precomputados en station_similarity, metadatos de candidatos y picks de
exploración. Todas las queries están cubiertas por índices existentes
(idx_plays_user/client_station_day, idx_plays_station_played,
idx_station_similarity_lookup).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, TypedDict

from sqlalchemy import select, text

from app.models.station import Station

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CandidateMeta(TypedDict):
    """Metadatos de una candidata para el blend del scoring."""

    quality: int
    language: str | None
    country: str | None
    click_trend: float
    plays_30d: int


async def get_seed_plays(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    client_id: uuid.UUID | None,
) -> list[tuple[uuid.UUID, int, float]]:
    """[(station_id, plays_90d, días_desde_último_play)] de la identidad."""
    if user_id is not None:
        where, params = "user_id = :ident", {"ident": str(user_id)}
    elif client_id is not None:
        where, params = "client_id = :ident", {"ident": str(client_id)}
    else:
        return []
    rows = (
        await session.execute(
            text(
                f"""
                SELECT station_id, COUNT(*) AS plays,
                       EXTRACT(EPOCH FROM (now() - MAX(played_at))) / 86400.0 AS days_ago
                FROM station_plays
                WHERE {where}
                GROUP BY station_id
                """,  # noqa: S608 — where es uno de dos literales internos
            ),
            params,
        )
    ).all()
    return [(uuid.UUID(str(r[0])), int(r[1]), float(r[2])) for r in rows]


async def get_user_marked_stations(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> tuple[set[uuid.UUID], set[uuid.UUID]]:
    """(favoritos, votados) del usuario."""
    favs = {
        uuid.UUID(str(r[0]))
        for r in (
            await session.execute(
                text("SELECT station_id FROM user_favorites WHERE user_id = :u"),
                {"u": str(user_id)},
            )
        ).all()
    }
    votes = {
        uuid.UUID(str(r[0]))
        for r in (
            await session.execute(
                text("SELECT station_id FROM user_votes WHERE user_id = :u"),
                {"u": str(user_id)},
            )
        ).all()
    }
    return favs, votes


async def get_neighbors(
    session: AsyncSession,
    station_ids: list[uuid.UUID],
) -> list[tuple[uuid.UUID, uuid.UUID, float]]:
    """Vecinos precomputados [(semilla, candidata, sim)] de las semillas."""
    if not station_ids:
        return []
    rows = (
        await session.execute(
            text(
                """
                SELECT station_id, similar_station_id, score
                FROM station_similarity
                WHERE station_id = ANY(CAST(:ids AS uuid[]))
                ORDER BY station_id, rank
                """,
            ),
            {"ids": [str(i) for i in station_ids]},
        )
    ).all()
    return [(uuid.UUID(str(r[0])), uuid.UUID(str(r[1])), float(r[2])) for r in rows]


async def get_candidate_meta(
    session: AsyncSession,
    station_ids: list[uuid.UUID],
) -> dict[uuid.UUID, CandidateMeta]:
    """Metadatos del blend para candidatas activas y visibles."""
    if not station_ids:
        return {}
    rows = (
        await session.execute(
            text(
                """
                SELECT s.id, s.quality_score, s.language, s.country_code,
                       s.click_trend, COALESCE(p.plays_30d, 0)
                FROM stations s
                LEFT JOIN (
                    SELECT station_id, COUNT(*) AS plays_30d
                    FROM station_plays
                    WHERE played_at >= now() - INTERVAL '30 days'
                      AND station_id = ANY(CAST(:ids AS uuid[]))
                    GROUP BY station_id
                ) p ON p.station_id = s.id
                WHERE s.id = ANY(CAST(:ids AS uuid[]))
                  AND s.status = 'active' AND NOT s.hidden
                """,
            ),
            {"ids": [str(i) for i in station_ids]},
        )
    ).all()
    return {
        uuid.UUID(str(r[0])): CandidateMeta(
            quality=int(r[1]) if r[1] is not None else 0,
            language=str(r[2]) if r[2] is not None else None,
            country=str(r[3]) if r[3] is not None else None,
            click_trend=float(r[4]) if r[4] is not None else 0.0,
            plays_30d=int(r[5]),
        )
        for r in rows
    }


async def get_genre_weights(
    session: AsyncSession,
    station_ids: list[uuid.UUID],
) -> dict[uuid.UUID, dict[int, float]]:
    """Vector disperso género->peso por emisora, con propagación 0.5 al padre."""
    if not station_ids:
        return {}
    rows = (
        await session.execute(
            text(
                """
                SELECT sg.station_id, sg.genre_id, sg.confidence, g.parent_id
                FROM station_genres sg
                JOIN genres g ON g.id = sg.genre_id
                WHERE sg.station_id = ANY(CAST(:ids AS uuid[]))
                """,
            ),
            {"ids": [str(i) for i in station_ids]},
        )
    ).all()
    vectors: dict[uuid.UUID, dict[int, float]] = {}
    for r in rows:
        sid = uuid.UUID(str(r[0]))
        gid, conf = int(r[1]), int(r[2]) / 100.0
        parent = int(r[3]) if r[3] is not None else None
        vec = vectors.setdefault(sid, {})
        vec[gid] = max(vec.get(gid, 0.0), conf)
        if parent is not None:
            vec[parent] = max(vec.get(parent, 0.0), 0.5 * conf)
    return vectors


async def get_primary_genres(
    session: AsyncSession,
    station_ids: list[uuid.UUID],
) -> dict[uuid.UUID, int]:
    """Género primario (mayor confidence) por emisora — para apply_genre_cap."""
    if not station_ids:
        return {}
    rows = (
        await session.execute(
            text(
                """
                SELECT DISTINCT ON (sg.station_id) sg.station_id, sg.genre_id
                FROM station_genres sg
                JOIN genres g ON g.id = sg.genre_id
                WHERE sg.station_id = ANY(CAST(:ids AS uuid[]))
                ORDER BY sg.station_id, sg.confidence DESC, g.sort_order ASC
                """,
            ),
            {"ids": [str(i) for i in station_ids]},
        )
    ).all()
    return {uuid.UUID(str(r[0])): int(r[1]) for r in rows}


async def get_exploration_picks(
    session: AsyncSession,
    *,
    genre_ids: list[int],
    exclude: list[uuid.UUID],
    limit: int,
) -> list[uuid.UUID]:
    """Emisoras curated de calidad y baja exposición, compatibles con el perfil.

    "Baja exposición" = menor local_plays_total primero; el desempate
    aleatorio rota qué emisoras frescas entran en los slots de exploración.
    """
    if not genre_ids:
        return []
    rows = (
        await session.execute(
            text(
                """
                SELECT s.id
                FROM stations s
                WHERE s.status = 'active' AND NOT s.hidden AND s.curated
                  AND s.quality_score >= 50
                  AND s.id != ALL(CAST(:exclude AS uuid[]))
                  AND EXISTS (
                      SELECT 1 FROM station_genres sg
                      WHERE sg.station_id = s.id
                        AND sg.genre_id = ANY(CAST(:genres AS int[]))
                  )
                ORDER BY s.local_plays_total ASC, RANDOM()
                LIMIT :lim
                """,
            ),
            {
                "exclude": [str(i) for i in exclude],
                "genres": genre_ids,
                "lim": limit,
            },
        )
    ).all()
    return [uuid.UUID(str(r[0])) for r in rows]


async def get_cold_start_ids(
    session: AsyncSession,
    *,
    country: str | None,
    language: str | None,
    limit: int,
) -> list[uuid.UUID]:
    """Mejores emisoras del país/idioma del visitante, por quality."""
    if country is None and language is None:
        return []
    rows = (
        await session.execute(
            text(
                """
                SELECT id
                FROM stations
                WHERE status = 'active' AND NOT hidden
                  AND (
                      country_code = CAST(:cc AS text)
                      OR language = CAST(:lang AS text)
                  )
                ORDER BY quality_score DESC, name ASC
                LIMIT :lim
                """,
            ),
            {"cc": country, "lang": language, "lim": limit},
        )
    ).all()
    return [uuid.UUID(str(r[0])) for r in rows]


async def get_similar_ids(
    session: AsyncSession,
    station_id: uuid.UUID,
    *,
    limit: int,
) -> list[uuid.UUID]:
    """Vecinos públicos (activos y visibles) de una emisora, por rank."""
    rows = (
        await session.execute(
            text(
                """
                SELECT ss.similar_station_id
                FROM station_similarity ss
                JOIN stations s ON s.id = ss.similar_station_id
                WHERE ss.station_id = :sid
                  AND s.status = 'active' AND NOT s.hidden
                ORDER BY ss.rank
                LIMIT :lim
                """,
            ),
            {"sid": str(station_id), "lim": limit},
        )
    ).all()
    return [uuid.UUID(str(r[0])) for r in rows]


async def get_stations_by_ids(
    session: AsyncSession,
    station_ids: list[uuid.UUID],
) -> dict[uuid.UUID, Station]:
    """Hidrata ORM Stations (con genres/streams) preservando lookup por id."""
    if not station_ids:
        return {}
    stmt = select(Station).where(Station.id.in_(station_ids))
    result = await session.execute(stmt)
    return {s.id: s for s in result.scalars().unique().all()}


async def insert_rec_events(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    client_id: uuid.UUID | None,
    surface: str,
    variant: str | None,
    events: list[dict[str, Any]],
) -> int:
    """Inserta impresiones/clicks. Ignora station_ids inexistentes (FK)."""
    inserted = 0
    stmt = text(
        """
        INSERT INTO rec_events
            (station_id, user_id, client_id, event_type, surface, variant, slot)
        SELECT :sid, :uid, :cid, :etype, :surface, :variant, :slot
        WHERE EXISTS (SELECT 1 FROM stations WHERE id = :sid)
        """,
    )
    for ev in events:
        result = await session.execute(
            stmt,
            {
                "sid": str(ev["station_id"]),
                "uid": str(user_id) if user_id else None,
                "cid": str(client_id) if client_id else None,
                "etype": ev["event_type"],
                "surface": surface,
                "variant": variant,
                "slot": ev.get("slot"),
            },
        )
        inserted += int(getattr(result, "rowcount", 0) or 0)
    await session.commit()
    return inserted
