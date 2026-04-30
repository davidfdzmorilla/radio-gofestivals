from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.api.deps import RedisDep, SessionDep, UserDep
from app.core.logging import get_logger
from app.repos import user_votes as votes_repo
from app.schemas.user import LikeResponse
from app.services.rate_limit import check_rate_limit

router = APIRouter(prefix="/stations", tags=["user-votes"])
log = get_logger("app.user.votes")

LIKE_LIMIT, LIKE_WINDOW = 10, 60


async def _ensure_station_exists(
    session, station_id: uuid.UUID,  # noqa: ANN001
) -> None:
    exists = (
        await session.execute(
            text("SELECT 1 FROM stations WHERE id = :sid"),
            {"sid": str(station_id)},
        )
    ).first()
    if exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="station_not_found",
        )


@router.post(
    "/{station_id}/like",
    response_model=LikeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def like_station(
    station_id: uuid.UUID,
    user: UserDep,
    session: SessionDep,
    redis: RedisDep,
) -> LikeResponse:
    allowed, _ = await check_rate_limit(
        redis,
        f"user_like:{user.id}",
        limit=LIKE_LIMIT,
        window_seconds=LIKE_WINDOW,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate_limit_exceeded",
        )

    await _ensure_station_exists(session, station_id)
    _, count = await votes_repo.add_vote(session, user.id, station_id)
    await session.commit()
    return LikeResponse(user_voted=True, votes_local=count)


@router.delete("/{station_id}/like", response_model=LikeResponse)
async def unlike_station(
    station_id: uuid.UUID,
    user: UserDep,
    session: SessionDep,
) -> LikeResponse:
    await _ensure_station_exists(session, station_id)
    _, count = await votes_repo.remove_vote(session, user.id, station_id)
    await session.commit()
    return LikeResponse(user_voted=False, votes_local=count)
