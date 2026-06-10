from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse

from app.api.deps import (
    OptionalUserDep,
    RedisDep,
    SessionDep,
    SettingsDep,
)
from app.core.logging import get_logger
from app.schemas.station import (
    CountryFacet,
    NearbyStation,
    StationDetail,
    StationsPage,
    StationSummary,
)
from app.schemas.station_play import PlayRegisterRequest, PlayRegisterResponse
from app.services import recommendations as recs_service
from app.services import stations as stations_service
from app.services.rate_limit import check_rate_limit

router = APIRouter(prefix="/stations", tags=["stations"])
log = get_logger("app.api.stations")

STREAM_RATE_LIMIT = 60
STREAM_RATE_WINDOW = 60

PLAY_RATE_LIMIT = 100
PLAY_RATE_WINDOW = 60


@router.get("", response_model=StationsPage)
async def list_stations(
    session: SessionDep,
    user: OptionalUserDep,
    ids: Annotated[str | None, Query(max_length=2000)] = None,
    genre: Annotated[str | None, Query()] = None,
    country: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
    curated: Annotated[bool | None, Query()] = None,
    q: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> StationsPage:
    if ids is not None:
        # Lookup por ids (favoritos anónimos): ignora el resto de filtros.
        try:
            parsed = [uuid.UUID(part) for part in ids.split(",") if part][:50]
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="invalid_ids",
            ) from exc
        return await stations_service.list_stations_by_ids(session, parsed)
    return await stations_service.list_stations(
        session,
        genre=genre,
        country=country,
        curated=curated,
        q=q,
        page=page,
        size=size,
        user_id=user.id if user else None,
    )


@router.get("/nearby", response_model=list[NearbyStation])
async def nearby_stations(
    session: SessionDep,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lng: Annotated[float, Query(ge=-180, le=180)],
    radius_km: Annotated[float, Query(gt=0, le=500)] = 50,
) -> list[NearbyStation]:
    return await stations_service.find_nearby(
        session,
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        limit=50,
    )


@router.get("/featured", response_model=StationsPage)
async def list_featured(
    session: SessionDep,
    size: Annotated[int, Query(ge=1, le=24)] = 12,
) -> StationsPage:
    return await stations_service.list_featured_stations(session, size=size)


@router.get("/facets/countries", response_model=list[CountryFacet])
async def country_facets(
    session: SessionDep,
    genre: Annotated[str | None, Query(max_length=100)] = None,
) -> list[CountryFacet]:
    """Países del catálogo activo con conteo de emisoras.

    Alimenta las páginas programáticas de país y el sitemap: ambos deben
    aplicar el gate de publicación sobre estos mismos conteos.
    """
    return await stations_service.list_country_facets(session, genre=genre)


@router.get("/trending", response_model=StationsPage)
async def list_trending(
    session: SessionDep,
    genre: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
) -> StationsPage:
    """Emisoras con click_trend positivo, ordenadas por tendencia."""
    return await stations_service.list_trending_stations(
        session,
        genre=genre,
        limit=limit,
    )


@router.get("/new", response_model=StationsPage)
async def list_new(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
) -> StationsPage:
    """Últimas emisoras incorporadas al catálogo activo."""
    return await stations_service.list_new_stations(session, limit=limit)


@router.get("/recommended", response_model=StationsPage)
async def list_recommended(
    session: SessionDep,
    redis: RedisDep,
    user: OptionalUserDep,
    client_id: Annotated[uuid.UUID | None, Query()] = None,
    locale: Annotated[str | None, Query(max_length=20)] = None,
    size: Annotated[int, Query(ge=1, le=24)] = 12,
) -> StationsPage:
    """Recomendaciones personalizadas por identidad (JWT > client_id).

    Sin identidad o sin historial devuelve el cold start del locale
    (país/idioma) — nunca una lista vacía mientras haya catálogo.
    """
    user_id = user.id if user else None
    effective_client = client_id if user is None else None
    return await recs_service.get_recommendations(
        session,
        redis,
        user_id=user_id,
        client_id=effective_client,
        locale=locale,
        size=size,
    )


@router.get("/{slug}", response_model=StationDetail)
async def station_detail(
    slug: str,
    session: SessionDep,
    redis: RedisDep,
    settings: SettingsDep,
    user: OptionalUserDep,
) -> StationDetail:
    detail = await stations_service.get_station_detail(
        session,
        redis,
        slug,
        ttl=settings.redis_cache_ttl,
        user_id=user.id if user else None,
    )
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="station_not_found")
    return detail


@router.get("/{slug}/similar", response_model=list[StationSummary])
async def similar_stations(
    slug: str,
    session: SessionDep,
    redis: RedisDep,
    size: Annotated[int, Query(ge=1, le=12)] = 6,
) -> list[StationSummary]:
    """Vecinas precomputadas de una emisora (station_similarity)."""
    summaries = await recs_service.get_similar_stations(
        session,
        redis,
        slug=slug,
        size=size,
    )
    if summaries is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="station_not_found",
        )
    return summaries


@router.post("/{slug}/play", response_model=PlayRegisterResponse)
async def register_play(
    slug: str,
    body: PlayRegisterRequest,
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    user: OptionalUserDep,
) -> PlayRegisterResponse:
    """Register a play event for an identified listener.

    Identity resolution: a valid Authorization header (JWT) always wins
    over a client_id in the body. If neither is present, the request is
    rejected with 400 — the client must mint a client_id (uuid v4 in
    localStorage) after consent. Daily dedup at the DB level means
    calling this twice for the same (identity, station) on the same UTC
    day is safe — the second call is a no-op and returns
    deduplicated=true.
    """
    client_ip = request.client.host if request.client else "unknown"
    allowed, _count = await check_rate_limit(
        redis,
        f"play:{client_ip}",
        limit=PLAY_RATE_LIMIT,
        window_seconds=PLAY_RATE_WINDOW,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate_limit_exceeded",
        )

    user_id = user.id if user else None
    client_id = body.client_id if user is None else None
    if user_id is None and client_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="identity_required",
        )

    found, was_new = await stations_service.register_play_for_slug(
        session,
        slug=slug,
        user_id=user_id,
        client_id=client_id,
    )
    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="station_not_found",
        )
    return PlayRegisterResponse(accepted=True, deduplicated=not was_new)


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
