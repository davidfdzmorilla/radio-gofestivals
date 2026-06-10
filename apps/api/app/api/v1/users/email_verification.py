from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import RedisDep, SessionDep, UserDep
from app.core.logging import get_logger
from app.schemas.user import VerifyEmailRequest
from app.services import email_verification as verification_service
from app.services.email_verification import InvalidVerificationTokenError
from app.services.rate_limit import check_rate_limit

router = APIRouter(prefix="/auth", tags=["user-auth"])
log = get_logger("app.user.email_verification")

RESEND_LIMIT, RESEND_WINDOW = 3, 60 * 60


def _public_base_url() -> str:
    return os.getenv("PUBLIC_BASE_URL", "https://radio.gofestivals.eu")


@router.post("/verify-email")
async def verify_email(
    body: VerifyEmailRequest,
    session: SessionDep,
) -> dict[str, bool]:
    """Consume el token del email y marca la cuenta como verificada."""
    try:
        await verification_service.verify(session, body.token)
    except InvalidVerificationTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_or_expired_token",
        ) from exc
    return {"ok": True}


@router.post("/resend-verification")
async def resend_verification(
    request: Request,
    user: UserDep,
    session: SessionDep,
    redis: RedisDep,
) -> dict[str, bool]:
    """Reenvía el email de verificación al usuario autenticado."""
    allowed, _ = await check_rate_limit(
        redis,
        f"verify_resend:{user.id}",
        limit=RESEND_LIMIT,
        window_seconds=RESEND_WINDOW,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate_limit_exceeded",
        )
    _ = request
    sent = await verification_service.request_verification(
        session,
        user,
        base_url=_public_base_url(),
    )
    return {"ok": True, "sent": sent}
