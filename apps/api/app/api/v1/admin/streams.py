from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminDep, RedisDep, SessionDep
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
from app.services.rate_limit import check_rate_limit

streams_router = APIRouter(prefix="/streams", tags=["admin-streams"])
bulk_router = APIRouter(prefix="/stations", tags=["admin-streams"])
log = get_logger("app.admin.streams")

# Mutaciones admin con efecto masivo: límite por admin, generoso para
# trabajo manual pero corta un script descontrolado o un token robado.
ADMIN_OPS_LIMIT, ADMIN_OPS_WINDOW = 30, 60


async def _ensure_within_limit(redis: RedisDep, admin_id: uuid.UUID) -> None:
    allowed, _ = await check_rate_limit(
        redis,
        f"admin_stream_ops:{admin_id}",
        limit=ADMIN_OPS_LIMIT,
        window_seconds=ADMIN_OPS_WINDOW,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate_limit_exceeded",
        )


@streams_router.patch(
    "/{stream_id}/promote-primary",
    response_model=PromotePrimaryResponse,
)
async def promote_primary(
    stream_id: uuid.UUID,
    admin: AdminDep,
    session: SessionDep,
    redis: RedisDep,
) -> PromotePrimaryResponse:
    await _ensure_within_limit(redis, admin.id)
    try:
        result = await stream_ops.promote_stream_to_primary(
            session,
            stream_id=stream_id,
            admin_id=admin.id,
        )
    except StreamNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="stream_not_found",
        ) from exc
    except AlreadyPrimaryError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="already_primary",
        ) from exc

    log.info(
        "stream_promoted_to_primary",
        admin_id=str(admin.id),
        stream_id=str(result["promoted_stream_id"]),
        station_id=str(result["station_id"]),
        demoted=str(result["demoted_stream_id"]) if result["demoted_stream_id"] else None,
    )
    return PromotePrimaryResponse(**result)


@bulk_router.post(
    "/bulk-status-change",
    response_model=BulkStatusChangeResponse,
)
async def bulk_status_change(
    body: BulkStatusChangeRequest,
    admin: AdminDep,
    session: SessionDep,
    redis: RedisDep,
) -> BulkStatusChangeResponse:
    await _ensure_within_limit(redis, admin.id)
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
