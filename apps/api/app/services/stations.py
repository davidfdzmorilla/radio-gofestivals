from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING

from app.repos import stations as stations_repo
from app.schemas.station import (
    NearbyStation,
    NowPlayingEntry,
    StationDetail,
    StationGenreRef,
    StationsPage,
    StationSummary,
)

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.station import Station


def _to_summary(station: Station) -> StationSummary:
    return StationSummary(
        id=station.id,
        slug=station.slug,
        name=station.name,
        country_code=station.country_code,
        city=station.city,
        codec=station.codec,
        bitrate=station.bitrate,
        curated=station.curated,
        quality_score=station.quality_score,
        genres=[g.slug for g in station.genres],
    )


async def list_stations(
    session: AsyncSession,
    *,
    genre: str | None,
    country: str | None,
    curated: bool | None,
    q: str | None,
    page: int,
    size: int,
) -> StationsPage:
    items, total = await stations_repo.list_active_stations(
        session,
        genre=genre,
        country=country,
        curated=curated,
        q=q,
        page=page,
        size=size,
    )
    return StationsPage(
        items=[_to_summary(s) for s in items],
        total=total,
        page=page,
        size=size,
        pages=max(1, math.ceil(total / size)) if total else 0,
    )


def _detail_cache_key(slug: str) -> str:
    return f"station:detail:{slug}:v1"


async def get_station_detail(
    session: AsyncSession,
    redis: Redis[str],
    slug: str,
    ttl: int,
) -> StationDetail | None:
    cached = await redis.get(_detail_cache_key(slug))
    if cached is not None:
        return StationDetail.model_validate(json.loads(cached))

    station = await stations_repo.get_active_station_by_slug(session, slug)
    if station is None:
        return None

    now_playing = await stations_repo.last_now_playing(session, station.id, limit=10)

    detail = StationDetail(
        id=station.id,
        slug=station.slug,
        name=station.name,
        homepage_url=station.homepage_url,
        country_code=station.country_code,
        city=station.city,
        codec=station.codec,
        bitrate=station.bitrate,
        language=station.language,
        curated=station.curated,
        quality_score=station.quality_score,
        status=station.status,
        genres=[
            StationGenreRef(slug=g.slug, name=g.name, color_hex=g.color_hex)
            for g in station.genres
        ],
        now_playing=[
            NowPlayingEntry(title=np.title, artist=np.artist, captured_at=np.captured_at)
            for np in now_playing
        ],
    )
    await redis.set(_detail_cache_key(slug), detail.model_dump_json(), ex=ttl)
    return detail


async def get_stream_url(session: AsyncSession, slug: str) -> tuple[str, str] | None:
    station = await stations_repo.get_active_station_by_slug(session, slug)
    if station is None:
        return None
    return str(station.id), station.stream_url


async def find_nearby(
    session: AsyncSession,
    *,
    lat: float,
    lng: float,
    radius_km: float,
    limit: int = 50,
) -> list[NearbyStation]:
    rows = await stations_repo.find_nearby(
        session, lat=lat, lng=lng, radius_km=radius_km, limit=limit,
    )
    return [
        NearbyStation(
            id=row.id,
            slug=row.slug,
            name=row.name,
            country_code=row.country_code,
            city=row.city,
            codec=row.codec,
            bitrate=row.bitrate,
            curated=row.curated,
            quality_score=row.quality_score,
            genres=[],
            distance_km=round(row.distance_km, 3),
        )
        for row in rows
    ]
