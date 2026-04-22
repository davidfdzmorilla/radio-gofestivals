from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.security import issue_access_token, verify_password
from app.repos import admins as admins_repo

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.config import Settings
    from app.models.admin import Admin


async def authenticate(
    session: AsyncSession,
    email: str,
    password: str,
    settings: Settings,
) -> tuple[Admin, str, datetime] | None:
    admin = await admins_repo.get_by_email(session, email)
    if admin is None:
        return None
    if not admin.active:
        return None
    if not verify_password(password, admin.password_hash):
        return None
    token, expires_at = issue_access_token(admin.id, admin.email, settings)
    await admins_repo.update_last_login(session, admin.id)
    return admin, token, expires_at
