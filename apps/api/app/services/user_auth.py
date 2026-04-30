from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from app.core.security import (
    hash_password,
    issue_user_token,
    verify_password,
)
from app.repos import users as users_repo

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.config import Settings
    from app.models.user import User


class EmailAlreadyRegisteredError(Exception):
    """Raised when register() is called with an email already in use."""


class InvalidCredentialsError(Exception):
    """Raised by authenticate() when email or password do not match."""


async def register(
    session: AsyncSession,
    *,
    email: str,
    password: str,
) -> User:
    existing = await users_repo.get_user_by_email(session, email)
    if existing is not None:
        raise EmailAlreadyRegisteredError(email)
    return await users_repo.create_user(
        session,
        email=email,
        password_hash=hash_password(password),
    )


async def authenticate(
    session: AsyncSession,
    *,
    email: str,
    password: str,
) -> User:
    user = await users_repo.get_user_by_email(session, email)
    if user is None:
        raise InvalidCredentialsError
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError
    return user


def mint_token(
    user: User, settings: Settings,
) -> tuple[str, datetime]:
    return issue_user_token(user.id, user.email, settings)


async def delete_account(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    password: str,
) -> bool:
    """Verify the password and soft-delete the account.

    The reauth-with-password requirement adds defense in depth: a stolen
    JWT can't nuke the account by itself.
    """
    user = await users_repo.get_user_by_id(session, user_id)
    if user is None:
        return False
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError
    await users_repo.soft_delete(session, user_id)
    return True
