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
    StationStreamRef,
    StationSummary,
)

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.station import Station
    from app.models.station_stream import StationStream


def _stream_ref(s: StationStream) -> StationStreamRef:
    return StationStreamRef(
        id=s.id,
        url=s.stream_url,
        codec=s.codec,
        bitrate=s.bitrate,
        format=s.format,
        is_primary=s.is_primary,
    )


def _primary_of(station: Station) -> StationStream | None:
    for s in station.streams:
        if s.is_primary:
            return s
    return station.streams[0] if station.streams else None


def _to_summary(station: Station) -> StationSummary:
    primary = _primary_of(station)
    return StationSummary(
        id=station.id,
        slug=station.slug,
        name=station.name,
        country_code=station.country_code,
        city=station.city,
        curated=station.curated,
        quality_score=station.quality_score,
        genres=[g.slug for g in station.genres],
        primary_stream=_stream_ref(primary) if primary else None,
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
    # v2 = primary_stream/streams shape; bumped from v1 to invalidate stale
    # detail blobs left over from the legacy schema.
    return f"station:detail:{slug}:v2"


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
        language=station.language,
        curated=station.curated,
        quality_score=station.quality_score,
        status=station.status,
        genres=[
            StationGenreRef(slug=g.slug, name=g.name, color_hex=g.color_hex)
            for g in station.genres
        ],
        streams=[_stream_ref(s) for s in station.streams],
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
    primary = _primary_of(station)
    if primary is None:
        return None
    return str(station.id), primary.stream_url


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
    nearby: list[NearbyStation] = []
    for row in rows:
        primary = (
            StationStreamRef(
                id=row.stream_id,
                url=row.stream_url,
                codec=row.codec,
                bitrate=row.bitrate,
                format=row.codec,
                is_primary=True,
            )
            if row.stream_id is not None
            else None
        )
        nearby.append(
            NearbyStation(
                id=row.id,
                slug=row.slug,
                name=row.name,
                country_code=row.country_code,
                city=row.city,
                curated=row.curated,
                quality_score=row.quality_score,
                genres=[],
                primary_stream=primary,
                distance_km=round(row.distance_km, 3),
            ),
        )
    return nearby
