"""Verificación de email (plan de mejoras B4).

Mismo ciclo que password_reset: token de un solo uso por email (Resend).
Sin bloqueos duros: una cuenta sin verificar funciona igual — la columna
users.email_verified_at habilita límites/funciones futuras.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.repos import email_verification_tokens as tokens_repo
from app.repos import users as users_repo
from app.services.email_resend import send_verification_email

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.user import User

log = get_logger("app.email_verification")


class InvalidVerificationTokenError(Exception):
    """Token desconocido, usado o caducado."""


async def request_verification(
    session: AsyncSession,
    user: User,
    *,
    base_url: str,
) -> bool:
    """Emite un token y envía el email. No-op si ya está verificado.

    Best-effort por diseño: el fallo del proveedor de email no debe romper
    el flujo del caller (registro). Devuelve si el email salió.
    """
    if user.email_verified_at is not None:
        return False
    token = await tokens_repo.create_token(session, user_id=user.id)
    await session.commit()
    sent = await send_verification_email(
        to=user.email,
        token=str(token),
        base_url=base_url,
    )
    if not sent:
        log.warning("verification_email_not_sent", user_id=str(user.id))
    return sent


async def verify(session: AsyncSession, token: uuid.UUID) -> None:
    user_id = await tokens_repo.consume_token(session, token)
    if user_id is None:
        raise InvalidVerificationTokenError
    await users_repo.set_email_verified(session, user_id)
    await session.commit()
    log.info("email_verified", user_id=str(user_id))
