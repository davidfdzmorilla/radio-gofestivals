from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select, update

from app.models.user import User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    password_hash: str,
) -> User:
    user = User(email=email.lower(), password_hash=password_hash)
    session.add(user)
    await session.flush()
    return user


async def get_user_by_email(
    session: AsyncSession, email: str,
) -> User | None:
    stmt = select(User).where(
        User.email == email.lower(), User.deleted_at.is_(None),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_user_by_id(
    session: AsyncSession, user_id: uuid.UUID,
) -> User | None:
    stmt = select(User).where(
        User.id == user_id, User.deleted_at.is_(None),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def update_password(
    session: AsyncSession,
    user_id: uuid.UUID,
    password_hash: str,
) -> None:
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            password_hash=password_hash,
            updated_at=datetime.now(tz=UTC),
        ),
    )


async def soft_delete(
    session: AsyncSession, user_id: uuid.UUID,
) -> None:
    """Soft delete a user. Email is rotated to allow re-registration.

    The partial UNIQUE index on `email WHERE deleted_at IS NULL` only
    protects active rows, but rotating the email avoids any future
    cleanup job tripping on duplicates if the partial index is ever
    relaxed. Pattern: deleted_<id>@deleted.local.
    """
    now = datetime.now(tz=UTC)
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            deleted_at=now,
            updated_at=now,
            email=f"deleted_{user_id}@deleted.local",
            username=None,
        ),
    )
