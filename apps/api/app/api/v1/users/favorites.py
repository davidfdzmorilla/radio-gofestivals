from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.api.deps import RedisDep, SessionDep, UserDep
from app.core.logging import get_logger
from app.repos import user_favorites as fav_repo
from app.schemas.user import (
    FavoriteOut,
    FavoritesListResponse,
    FavoriteStreamRef,
    MigrateFavoritesRequest,
    MigrateFavoritesResponse,
)
from app.services.rate_limit import check_rate_limit

router = APIRouter(prefix="/favorites", tags=["user-favorites"])
log = get_logger("app.user.favorites")

MIGRATE_LIMIT, MIGRATE_WINDOW = 1, 60


def _row_to_out(row: dict) -> FavoriteOut:
    primary = None
    if row["primary_stream"] is not None:
        ps = row["primary_stream"]
        primary = FavoriteStreamRef(
            id=ps["id"],
            url=ps["url"],
            codec=ps["codec"],
            bitrate=ps["bitrate"],
            format=ps["format"],
        )
    return FavoriteOut(
        station_id=row["station_id"],
        slug=row["slug"],
        name=row["name"],
        country_code=row["country_code"],
        city=row["city"],
        curated=row["curated"],
        quality_score=row["quality_score"],
        status=row["status"],
        primary_stream=primary,
        created_at=row["created_at"],
    )


@router.get("", response_model=FavoritesListResponse)
async def list_favorites(
    user: UserDep, session: SessionDep,
) -> FavoritesListResponse:
    rows = await fav_repo.list_favorites(session, user.id)
    items = [_row_to_out(r) for r in rows]
    return FavoritesListResponse(items=items, total=len(items))


@router.post("/{station_id}", status_code=status.HTTP_201_CREATED)
async def add_favorite(
    station_id: uuid.UUID,
    user: UserDep,
    session: SessionDep,
) -> dict[str, bool]:
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
    added = await fav_repo.add_favorite(session, user.id, station_id)
    await session.commit()
    return {"added": added}


@router.delete(
    "/{station_id}", status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_favorite(
    station_id: uuid.UUID,
    user: UserDep,
    session: SessionDep,
) -> None:
    await fav_repo.remove_favorite(session, user.id, station_id)
    await session.commit()


@router.post("/migrate", response_model=MigrateFavoritesResponse)
async def migrate_favorites(
    body: MigrateFavoritesRequest,
    user: UserDep,
    session: SessionDep,
    redis: RedisDep,
) -> MigrateFavoritesResponse:
    allowed, _ = await check_rate_limit(
        redis,
        f"user_migrate_fav:{user.id}",
        limit=MIGRATE_LIMIT,
        window_seconds=MIGRATE_WINDOW,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate_limit_exceeded",
        )
    counts = await fav_repo.bulk_add_favorites(
        session, user.id, body.station_ids,
    )
    await session.commit()
    log.info(
        "user_favorites_migrated",
        user_id=str(user.id),
        added=counts["added"],
        already_existed=counts["already_existed"],
        invalid=counts["invalid"],
    )
    return MigrateFavoritesResponse(**counts)
