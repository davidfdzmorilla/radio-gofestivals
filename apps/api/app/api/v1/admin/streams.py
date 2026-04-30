from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminDep, SessionDep
from app.core.logging import get_logger
from app.schemas.admin_streams import (
    BulkStatusChangeRequest,
    BulkStatusChangeResponse,
    PromotePrimaryResponse,
)
from app.services.admin import stream_ops
from app.services.admin.stream_ops import (
    AlreadyPrimaryError,
    StreamNotFoundError,
)

streams_router = APIRouter(prefix="/streams", tags=["admin-streams"])
bulk_router = APIRouter(prefix="/stations", tags=["admin-streams"])
log = get_logger("app.admin.streams")


@streams_router.patch(
    "/{stream_id}/promote-primary",
    response_model=PromotePrimaryResponse,
)
async def promote_primary(
    stream_id: uuid.UUID,
    admin: AdminDep,
    session: SessionDep,
) -> PromotePrimaryResponse:
    try:
        result = await stream_ops.promote_stream_to_primary(
            session,
            stream_id=stream_id,
            admin_id=admin.id,
        )
    except StreamNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="stream_not_found",
        ) from exc
    except AlreadyPrimaryError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="already_primary",
        ) from exc

    log.info(
        "stream_promoted_to_primary",
        admin_id=str(admin.id),
        stream_id=str(result["promoted_stream_id"]),
        station_id=str(result["station_id"]),
        demoted=str(result["demoted_stream_id"])
        if result["demoted_stream_id"]
        else None,
    )
    return PromotePrimaryResponse(**result)


@bulk_router.post(
    "/bulk-status-change", response_model=BulkStatusChangeResponse,
)
async def bulk_status_change(
    body: BulkStatusChangeRequest,
    admin: AdminDep,
    session: SessionDep,
) -> BulkStatusChangeResponse:
    try:
        result = await stream_ops.bulk_change_status(
            session,
            station_ids=body.station_ids,
            new_status=body.new_status,
            reason=body.reason,
            admin_id=admin.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"validation_failed: {exc}",
        ) from exc

    log.info(
        "bulk_status_change",
        admin_id=str(admin.id),
        new_status=body.new_status,
        affected=result["affected"],
        skipped=result["skipped"],
    )
    return BulkStatusChangeResponse(**result)
