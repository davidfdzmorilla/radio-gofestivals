from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def create_token(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    expires_at: datetime,
) -> uuid.UUID:
    token = (
        await session.execute(
            text(
                """
                INSERT INTO password_reset_tokens (user_id, expires_at)
                VALUES (:uid, :exp)
                RETURNING token
                """,
            ),
            {"uid": str(user_id), "exp": expires_at},
        )
    ).scalar_one()
    return uuid.UUID(str(token))


async def consume_token(
    session: AsyncSession, token: uuid.UUID,
) -> uuid.UUID | None:
    """Return user_id if the token is valid (unused, not expired) and mark
    it consumed atomically. Returns None for any failure mode.
    """
    now = datetime.now(tz=UTC)
    row = (
        await session.execute(
            text(
                """
                UPDATE password_reset_tokens
                SET used_at = :now
                WHERE token = :tok
                  AND used_at IS NULL
                  AND expires_at > :now
                RETURNING user_id
                """,
            ),
            {"tok": str(token), "now": now},
        )
    ).first()
    return uuid.UUID(str(row[0])) if row is not None else None


async def invalidate_user_tokens(
    session: AsyncSession, user_id: uuid.UUID,
) -> int:
    """Invalidate all unused tokens for a user (used at password reset)."""
    now = datetime.now(tz=UTC)
    result = await session.execute(
        text(
            """
            UPDATE password_reset_tokens
            SET used_at = :now
            WHERE user_id = :uid AND used_at IS NULL
            """,
        ),
        {"uid": str(user_id), "now": now},
    )
    return int(result.rowcount or 0)
