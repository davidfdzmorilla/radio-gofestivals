from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse

from app.api.deps import RedisDep, SessionDep, SettingsDep
from app.core.logging import get_logger
from app.schemas.station import NearbyStation, StationDetail, StationsPage
from app.services import stations as stations_service
from app.services.rate_limit import check_rate_limit

router = APIRouter(prefix="/stations", tags=["stations"])
log = get_logger("app.api.stations")

STREAM_RATE_LIMIT = 60
STREAM_RATE_WINDOW = 60


@router.get("", response_model=StationsPage)
async def list_stations(
    session: SessionDep,
    genre: Annotated[str | None, Query()] = None,
    country: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
    curated: Annotated[bool | None, Query()] = None,
    q: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> StationsPage:
    return await stations_service.list_stations(
        session,
        genre=genre,
        country=country,
        curated=curated,
        q=q,
        page=page,
        size=size,
    )


@router.get("/nearby", response_model=list[NearbyStation])
async def nearby_stations(
    session: SessionDep,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lng: Annotated[float, Query(ge=-180, le=180)],
    radius_km: Annotated[float, Query(gt=0, le=500)] = 50,
) -> list[NearbyStation]:
    return await stations_service.find_nearby(
        session, lat=lat, lng=lng, radius_km=radius_km, limit=50,
    )


@router.get("/{slug}", response_model=StationDetail)
async def station_detail(
    slug: str,
    session: SessionDep,
    redis: RedisDep,
    settings: SettingsDep,
) -> StationDetail:
    detail = await stations_service.get_station_detail(
        session, redis, slug, ttl=settings.redis_cache_ttl,
    )
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="station_not_found")
    return detail


@router.get("/{slug}/stream")
async def station_stream(
    slug: str,
    request: Request,
    session: SessionDep,
    redis: RedisDep,
) -> RedirectResponse:
    client_ip = request.client.host if request.client else "unknown"
    allowed, count = await check_rate_limit(
        redis,
        f"stream:{client_ip}",
        limit=STREAM_RATE_LIMIT,
        window_seconds=STREAM_RATE_WINDOW,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate_limit_exceeded",
        )

    result = await stations_service.get_stream_url(session, slug)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="station_not_found")
    station_id, stream_url = result

    log.info(
        "stream_redirect",
        station_id=station_id,
        slug=slug,
        user_agent=request.headers.get("user-agent", ""),
        ip=client_ip,
        req_count=count,
    )
    return RedirectResponse(url=stream_url, status_code=status.HTTP_302_FOUND)
