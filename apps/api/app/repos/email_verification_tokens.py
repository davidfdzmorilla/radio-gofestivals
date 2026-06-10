"""Tokens de verificación de email (B4). Espejo de password_reset_tokens."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def create_token(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    ttl_hours: int = 48,
) -> uuid.UUID:
    token = (
        await session.execute(
            text(
                """
                INSERT INTO email_verification_tokens (user_id, expires_at)
                VALUES (:uid, :exp)
                RETURNING token
                """,
            ),
            {
                "uid": str(user_id),
                "exp": datetime.now(tz=UTC) + timedelta(hours=ttl_hours),
            },
        )
    ).scalar_one()
    return uuid.UUID(str(token))


async def consume_token(
    session: AsyncSession,
    token: uuid.UUID,
) -> uuid.UUID | None:
    """user_id si el token es válido (sin usar, no caducado); lo marca usado."""
    row = (
        await session.execute(
            text(
                """
                UPDATE email_verification_tokens
                SET used_at = now()
                WHERE token = :tok AND used_at IS NULL AND expires_at > now()
                RETURNING user_id
                """,
            ),
            {"tok": str(token)},
        )
    ).first()
    return uuid.UUID(str(row[0])) if row is not None else None
