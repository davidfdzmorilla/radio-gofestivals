from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import OptionalUserDep, RedisDep, SessionDep
from app.core.logging import get_logger
from app.repos import recommendations as recs_repo
from app.schemas.rec import RecEventsRequest, RecEventsResponse
from app.services.rate_limit import check_rate_limit

router = APIRouter(prefix="/recs", tags=["recommendations"])
log = get_logger("app.api.recs")

EVENTS_RATE_LIMIT = 30
EVENTS_RATE_WINDOW = 60


@router.post("/events", response_model=RecEventsResponse)
async def register_rec_events(
    body: RecEventsRequest,
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    user: OptionalUserDep,
) -> RecEventsResponse:
    """Impresiones y clicks del módulo de recomendaciones (evaluación §7)."""
    client_ip = request.client.host if request.client else "unknown"
    allowed, _ = await check_rate_limit(
        redis,
        f"recs_events:{client_ip}",
        limit=EVENTS_RATE_LIMIT,
        window_seconds=EVENTS_RATE_WINDOW,
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

    inserted = await recs_repo.insert_rec_events(
        session,
        user_id=user_id,
        client_id=client_id,
        surface=body.surface,
        variant=body.variant,
        events=[e.model_dump() for e in body.events],
    )
    return RecEventsResponse(inserted=inserted)
