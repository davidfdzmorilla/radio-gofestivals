from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import RedisDep, SessionDep, SettingsDep
from app.schemas.genre import GenreNode
from app.services.genres import get_genres_tree

router = APIRouter(prefix="/genres", tags=["genres"])


@router.get("", response_model=list[GenreNode])
async def list_genres(
    session: SessionDep,
    redis: RedisDep,
    settings: SettingsDep,
) -> list[GenreNode]:
    return await get_genres_tree(session, redis, ttl=settings.redis_genres_ttl)
