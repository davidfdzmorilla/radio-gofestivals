from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import RedisDep, SessionDep
from app.core.logging import get_logger
from app.schemas.user import ForgotPasswordRequest, ResetPasswordRequest
from app.services import password_reset as reset_service
from app.services.password_reset import InvalidResetTokenError
from app.services.rate_limit import check_rate_limit

router = APIRouter(prefix="/auth", tags=["user-auth"])
log = get_logger("app.user.password")

FORGOT_LIMIT, FORGOT_WINDOW = 3, 60 * 60


def _public_base_url() -> str:
    """URL del frontend público para construir el reset link.

    Lee `PUBLIC_BASE_URL` (.env.production) y cae a la URL prod actual
    si no está definida — preferible a fallar el endpoint silenciosamente.
    """
    return os.getenv("PUBLIC_BASE_URL", "https://radio.gofestivals.eu")


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    session: SessionDep,
    redis: RedisDep,
) -> dict[str, bool]:
    ip = request.client.host if request.client else "unknown"
    allowed, _ = await check_rate_limit(
        redis,
        f"user_forgot:{ip}",
        limit=FORGOT_LIMIT,
        window_seconds=FORGOT_WINDOW,
    )
    if not allowed:
        log.warning("user_forgot_rate_limited", ip=ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate_limit_exceeded",
        )

    await reset_service.request_reset(
        session, email=body.email, base_url=_public_base_url(),
    )
    # Anti-enumeration: same response whether the user exists or not.
    return {"ok": True}


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    session: SessionDep,
) -> dict[str, bool]:
    try:
        await reset_service.reset_password(
            session,
            token=body.token,
            new_password=body.new_password,
        )
    except InvalidResetTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_or_expired_token",
        ) from exc
    return {"ok": True}
