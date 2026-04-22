from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import AdminDep, RedisDep, SessionDep
from app.core.logging import get_logger
from app.schemas.admin import CurateResponse, CurationRequest, StationPendingPage
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
