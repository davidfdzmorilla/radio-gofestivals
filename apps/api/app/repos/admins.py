from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select, update

from app.models.admin import Admin

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


async def get_by_email(session: AsyncSession, email: str) -> Admin | None:
    stmt = select(Admin).where(Admin.email == email.lower())
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_by_id(session: AsyncSession, admin_id: uuid.UUID) -> Admin | None:
    stmt = select(Admin).where(Admin.id == admin_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def update_last_login(session: AsyncSession, admin_id: uuid.UUID) -> None:
    await session.execute(
        update(Admin).where(Admin.id == admin_id).values(last_login_at=datetime.now(tz=UTC)),
    )
