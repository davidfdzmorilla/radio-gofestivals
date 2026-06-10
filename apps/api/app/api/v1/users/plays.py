from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import SessionDep, UserDep
from app.core.logging import get_logger
from app.repos import station_plays as plays_repo
from app.schemas.station_play import (
    ErasePlaysResponse,
    MergePlaysRequest,
    MergePlaysResponse,
    PlayExportItem,
    PlaysExportResponse,
    UserExportInfo,
)

router = APIRouter(prefix="/me/plays", tags=["user-plays"])
log = get_logger("app.user.plays")


@router.post("/merge", response_model=MergePlaysResponse)
async def merge_plays(
    body: MergePlaysRequest,
    user: UserDep,
    session: SessionDep,
) -> MergePlaysResponse:
    """Reassign anonymous plays from a localStorage client_id to this account.

    Called by the client right after a successful login or registration,
    passing the client_id it minted during anonymous use. Idempotent: a
    second call with the same client_id moves nothing because the rows
    have already been re-attributed. Rows that would collide with an
    existing user_id play on the same UTC day are dropped (the data
    point already exists), not double-counted.
    """
    merged, dropped = await plays_repo.merge_anon_plays_to_user(
        session,
        user_id=user.id,
        client_id=body.client_id,
    )
    log.info(
        "plays_merged_anon_to_user",
        user_id=str(user.id),
        client_id=str(body.client_id),
        merged=merged,
        dropped_conflicts=dropped,
    )
    return MergePlaysResponse(merged=merged, dropped_conflicts=dropped)


@router.get("/export", response_model=PlaysExportResponse)
async def export_plays(
    user: UserDep,
    session: SessionDep,
) -> PlaysExportResponse:
    """GDPR Art. 15 right of access for the plays surface.

    Returns the user's profile fields and every play attributed to
    them, joined with station slug/name so the payload is self-explanatory
    without a follow-up call.
    """
    rows = await plays_repo.export_user_plays(session, user.id)
    return PlaysExportResponse(
        user=UserExportInfo(
            id=user.id,
            email=user.email,
            created_at=user.created_at,
        ),
        plays=[PlayExportItem(**row) for row in rows],
    )


@router.post("/erase", response_model=ErasePlaysResponse)
async def erase_plays(
    user: UserDep,
    session: SessionDep,
) -> ErasePlaysResponse:
    """GDPR Art. 17 right to erasure, scoped to the plays surface.

    Deletes every play row attributed to ``user.id``. The DELETE trigger
    decrements the denormalized counter so the catalog totals stay
    honest. Account-level deletion (``DELETE /api/v1/auth/me``) is a
    separate flow.
    """
    erased = await plays_repo.erase_user_plays(session, user.id)
    log.info(
        "plays_erased_for_user",
        user_id=str(user.id),
        erased=erased,
    )
    return ErasePlaysResponse(erased=erased)
