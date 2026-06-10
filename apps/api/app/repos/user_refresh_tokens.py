"""Refresh tokens rotatorios (plan de mejoras B3).

Solo se persiste el SHA-256 del token; el claro viaja en la cookie
httpOnly y nunca toca la DB ni los logs.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def create(
    session: AsyncSession,
    *,
    token_hash: str,
    user_id: uuid.UUID,
    ttl_days: int,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO user_refresh_tokens (token_hash, user_id, expires_at)
            VALUES (:h, :uid, :exp)
            """,
        ),
        {
            "h": token_hash,
            "uid": str(user_id),
            "exp": datetime.now(tz=UTC) + timedelta(days=ttl_days),
        },
    )


async def get_state(
    session: AsyncSession,
    token_hash: str,
) -> tuple[uuid.UUID, bool, bool] | None:
    """(user_id, vigente, revocado) del hash, o None si no existe.

    "Revocado" distingue el replay de un token rotado (señal de robo)
    del simple token caducado.
    """
    row = (
        await session.execute(
            text(
                """
                SELECT user_id,
                       (revoked_at IS NULL AND expires_at > now()) AS valid,
                       (revoked_at IS NOT NULL) AS revoked
                FROM user_refresh_tokens
                WHERE token_hash = :h
                """,
            ),
            {"h": token_hash},
        )
    ).first()
    if row is None:
        return None
    return uuid.UUID(str(row[0])), bool(row[1]), bool(row[2])


async def rotate(
    session: AsyncSession,
    *,
    old_hash: str,
    new_hash: str,
    user_id: uuid.UUID,
    ttl_days: int,
) -> None:
    """Revoca el token actual apuntando a su sucesor e inserta el nuevo."""
    await session.execute(
        text(
            """
            UPDATE user_refresh_tokens
            SET revoked_at = now(), replaced_by_hash = :new
            WHERE token_hash = :old AND revoked_at IS NULL
            """,
        ),
        {"old": old_hash, "new": new_hash},
    )
    await create(session, token_hash=new_hash, user_id=user_id, ttl_days=ttl_days)


async def revoke(session: AsyncSession, token_hash: str) -> None:
    await session.execute(
        text(
            """
            UPDATE user_refresh_tokens
            SET revoked_at = now()
            WHERE token_hash = :h AND revoked_at IS NULL
            """,
        ),
        {"h": token_hash},
    )


async def revoke_all_for_user(session: AsyncSession, user_id: uuid.UUID) -> int:
    """Cierra todas las sesiones del usuario (reuse detection, reset, baja)."""
    result = await session.execute(
        text(
            """
            UPDATE user_refresh_tokens
            SET revoked_at = now()
            WHERE user_id = :uid AND revoked_at IS NULL
            """,
        ),
        {"uid": str(user_id)},
    )
    return int(getattr(result, "rowcount", 0) or 0)
