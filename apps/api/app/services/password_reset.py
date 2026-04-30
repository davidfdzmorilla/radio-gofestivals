from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.core.security import hash_password
from app.repos import password_reset_tokens as tokens_repo
from app.repos import users as users_repo
from app.services.email_resend import send_password_reset_email

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


TOKEN_TTL = timedelta(hours=1)


async def request_reset(
    session: AsyncSession,
    *,
    email: str,
    base_url: str,
) -> bool:
    """Send a reset email if the address belongs to a real user.

    Always returns True to defeat email enumeration (caller maps to 200).
    Email delivery is best-effort: a Resend outage doesn't surface to
    the user.
    """
    user = await users_repo.get_user_by_email(session, email)
    if user is None:
        return True

    expires_at = datetime.now(tz=UTC) + TOKEN_TTL
    token = await tokens_repo.create_token(
        session, user_id=user.id, expires_at=expires_at,
    )
    await session.commit()

    await send_password_reset_email(
        to=user.email, token=str(token), base_url=base_url,
    )
    return True


class InvalidResetTokenError(Exception):
    """Token does not exist, is expired, or has already been used."""


async def reset_password(
    session: AsyncSession,
    *,
    token: uuid.UUID,
    new_password: str,
) -> None:
    user_id = await tokens_repo.consume_token(session, token)
    if user_id is None:
        raise InvalidResetTokenError

    await users_repo.update_password(
        session,
        user_id,
        hash_password(new_password),
    )
    # Invalidate any other pending reset tokens — a successful reset
    # should make older outstanding emails dead links.
    await tokens_repo.invalidate_user_tokens(session, user_id)
    await session.commit()
