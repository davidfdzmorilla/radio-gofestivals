from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.redis import get_redis
from app.core.security import (
    TokenError,
    decode_access_token,
    decode_user_token,
)
from app.models.admin import Admin
from app.models.user import User
from app.repos import admins as admins_repo
from app.repos import users as users_repo


def redis_dep() -> "Redis[str]":
    return get_redis()


def settings_dep() -> Settings:
    return get_settings()


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(settings_dep)]

if TYPE_CHECKING:
    RedisDep = Annotated[Redis[str], Depends(redis_dep)]
else:
    # Redis class no es subscriptable en runtime; FastAPI no necesita el [str]
    RedisDep = Annotated[Redis, Depends(redis_dep)]

_bearer = HTTPBearer(auto_error=False)


async def get_current_admin(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: SessionDep,
    settings: SettingsDep,
) -> Admin:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_token")
    try:
        payload = decode_access_token(creds.credentials, settings)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc),
        ) from exc

    try:
        admin_id = uuid.UUID(str(payload.get("sub", "")))
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token",
        ) from exc

    admin = await admins_repo.get_by_id(session, admin_id)
    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="admin_not_found")
    if not admin.active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin_inactive")
    return admin


AdminDep = Annotated[Admin, Depends(get_current_admin)]


async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: SessionDep,
    settings: SettingsDep,
) -> User:
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_token",
        )
    try:
        payload = decode_user_token(creds.credentials, settings)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc),
        ) from exc

    try:
        user_id = uuid.UUID(str(payload.get("sub", "")))
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token",
        ) from exc

    user = await users_repo.get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="user_not_found",
        )
    return user


UserDep = Annotated[User, Depends(get_current_user)]


async def get_optional_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: SessionDep,
    settings: SettingsDep,
) -> User | None:
    """Public endpoints can use this to fetch the current user when a JWT
    is present, returning None instead of raising on absence/invalid.
    """
    if creds is None or not creds.credentials:
        return None
    try:
        payload = decode_user_token(creds.credentials, settings)
    except TokenError:
        return None
    try:
        user_id = uuid.UUID(str(payload.get("sub", "")))
    except (ValueError, TypeError):
        return None
    return await users_repo.get_user_by_id(session, user_id)


OptionalUserDep = Annotated[User | None, Depends(get_optional_user)]
