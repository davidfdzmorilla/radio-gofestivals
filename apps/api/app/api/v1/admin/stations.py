from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import AdminDep, RedisDep, SessionDep
from app.core.logging import get_logger
from app.schemas.admin import (
    CurateResponse,
    CurationRequest,
    StationAdminDetail,
    StationListPage,
    StationPendingPage,
    StationUpdate,
)
from app.services.admin import stations as admin_stations_service

router = APIRouter(prefix="/stations", tags=["admin-stations"])
log = get_logger("app.admin.stations")


@router.get("/pending", response_model=StationPendingPage)
async def list_pending(
    admin: AdminDep,  # noqa: ARG001 — enforces auth
    session: SessionDep,
    country: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
    has_geo: Annotated[bool | None, Query()] = None,
    min_quality: Annotated[int | None, Query(ge=0, le=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> StationPendingPage:
    return await admin_stations_service.list_pending(
        session,
        country=country,
        has_geo=has_geo,
        min_quality=min_quality,
        page=page,
        size=size,
    )


@router.get("", response_model=StationListPage)
async def list_all(
    admin: AdminDep,  # noqa: ARG001 — enforces auth
    session: SessionDep,
    status_filter: Annotated[
        Literal["pending", "active", "broken", "rejected", "duplicate", "inactive"]
        | None,
        Query(alias="status"),
    ] = None,
    curated: Annotated[bool | None, Query()] = None,
    search: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> StationListPage:
    return await admin_stations_service.list_all(
        session,
        status=status_filter,
        curated=curated,
        search=search,
        page=page,
        size=size,
    )


@router.get("/{station_id}", response_model=StationAdminDetail)
async def get_station(
    station_id: uuid.UUID,
    admin: AdminDep,  # noqa: ARG001
    session: SessionDep,
) -> StationAdminDetail:
    detail = await admin_stations_service.get_detail(session, station_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="station_not_found",
        )
    return detail


@router.patch("/{station_id}", response_model=StationAdminDetail)
async def update_station(
    station_id: uuid.UUID,
    body: StationUpdate,
    admin: AdminDep,
    session: SessionDep,
    redis: RedisDep,
) -> StationAdminDetail:
    detail = await admin_stations_service.update_station(
        session,
        redis,
        admin_id=admin.id,
        station_id=station_id,
        payload=body,
    )
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="station_not_found",
        )
    log.info(
        "admin_station_updated",
        admin_id=str(admin.id),
        station_id=str(station_id),
        fields=[
            k for k in ("curated", "status", "name", "slug", "genre_ids")
            if getattr(body, k) is not None
        ],
    )
    return detail


@router.put("/{station_id}/curate", response_model=CurateResponse)
async def curate(
    station_id: uuid.UUID,
    body: CurationRequest,
    admin: AdminDep,
    session: SessionDep,
    redis: RedisDep,
) -> CurateResponse:
    if body.decision == "reclassify" and not body.genre_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="genre_ids_required_for_reclassify",
        )

    result = await admin_stations_service.apply_curation(
        session,
        redis,
        admin_id=admin.id,
        station_id=station_id,
        decision=body,
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="station_not_found")

    new_status, curated, log_id = result
    log.info(
        "curation_applied",
        admin_id=str(admin.id),
        station_id=str(station_id),
        decision=body.decision,
        log_id=log_id,
    )
    return CurateResponse(
        station_id=station_id,
        status=new_status,
        curated=curated,
        log_id=log_id,
    )
