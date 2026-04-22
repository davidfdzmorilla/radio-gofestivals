from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from sqlalchemy import bindparam, func, select, text

from app.models.genre import Genre
from app.models.station import NowPlaying, Station, StationGenre

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class NearbyRow(NamedTuple):
    id: uuid.UUID
    slug: str
    name: str
    country_code: str | None
    city: str | None
    codec: str | None
    bitrate: int | None
    curated: bool
    quality_score: int
    distance_km: float


async def list_active_stations(
    session: AsyncSession,
    *,
    genre: str | None,
    country: str | None,
    curated: bool | None,
    q: str | None,
    page: int,
    size: int,
) -> tuple[list[Station], int]:
    base = select(Station).where(Station.status == "active")

    if genre is not None:
        genre_stations = (
            select(StationGenre.station_id)
            .join(Genre, Genre.id == StationGenre.genre_id)
            .where(Genre.slug == genre)
        )
        base = base.where(Station.id.in_(genre_stations))
    if country is not None:
        base = base.where(Station.country_code == country.upper())
    if curated is not None:
        base = base.where(Station.curated.is_(curated))
    if q:
        base = base.where(
            text("name % :q").bindparams(bindparam("q", q)),
        ).order_by(text("similarity(name, :q) DESC").bindparams(bindparam("q", q)))
    else:
        base = base.order_by(Station.quality_score.desc(), Station.name.asc())

    total_stmt = select(func.count()).select_from(base.subquery())
    total = (await session.execute(total_stmt)).scalar_one()

    page_stmt = base.limit(size).offset((page - 1) * size)
    result = await session.execute(page_stmt)
    items = list(result.scalars().unique().all())
    return items, int(total)


async def get_active_station_by_slug(session: AsyncSession, slug: str) -> Station | None:
    stmt = select(Station).where(Station.slug == slug, Station.status == "active")
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_station_by_slug_any_status(session: AsyncSession, slug: str) -> Station | None:
    stmt = select(Station).where(Station.slug == slug)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def last_now_playing(
    session: AsyncSession,
    station_id: uuid.UUID,
    limit: int = 10,
) -> list[NowPlaying]:
    stmt = (
        select(NowPlaying)
        .where(NowPlaying.station_id == station_id)
        .order_by(NowPlaying.captured_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def find_nearby(
    session: AsyncSession,
    *,
    lat: float,
    lng: float,
    radius_km: float,
    limit: int = 50,
) -> list[NearbyRow]:
    stmt = text(
        """
        SELECT
            s.id, s.slug, s.name, s.country_code, s.city,
            s.codec, s.bitrate, s.curated, s.quality_score,
            ST_Distance(
                s.geo,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
            ) / 1000.0 AS distance_km
        FROM stations s
        WHERE s.status = 'active'
          AND s.geo IS NOT NULL
          AND ST_DWithin(
              s.geo,
              ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
              :radius_m
          )
        ORDER BY distance_km ASC
        LIMIT :limit
        """
    )
    result = await session.execute(
        stmt,
        {"lat": lat, "lng": lng, "radius_m": radius_km * 1000, "limit": limit},
    )
    return [NearbyRow(*row) for row in result.all()]
