from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import AdminDep, RedisDep, SessionDep, SettingsDep
from app.core.logging import get_logger
from app.schemas.admin import AccessToken, AdminLogin, AdminMe
from app.services.admin import auth as auth_service
from app.services.rate_limit import check_rate_limit

router = APIRouter(prefix="/auth", tags=["admin-auth"])
log = get_logger("app.admin.auth")

LOGIN_RATE_LIMIT = 5
LOGIN_RATE_WINDOW = 60


@router.post("/login", response_model=AccessToken)
async def login(
    body: AdminLogin,
    request: Request,
    session: SessionDep,
    redis: RedisDep,
    settings: SettingsDep,
) -> AccessToken:
    ip = request.client.host if request.client else "unknown"
    allowed, _count = await check_rate_limit(
        redis, f"admin_login:{ip}", limit=LOGIN_RATE_LIMIT, window_seconds=LOGIN_RATE_WINDOW,
    )
    if not allowed:
        log.warning("admin_login_rate_limited", ip=ip, email=body.email)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="rate_limit_exceeded",
        )

    result = await auth_service.authenticate(session, body.email, body.password, settings)
    if result is None:
        log.warning("admin_login_failed", ip=ip, email=body.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials",
        )

    admin, token, expires_at = result
    await session.commit()
    log.info("admin_login_ok", ip=ip, admin_id=str(admin.id), email=admin.email)
    return AccessToken(access_token=token, expires_at=expires_at)


@router.get("/me", response_model=AdminMe)
async def me(admin: AdminDep) -> AdminMe:
    return AdminMe(
        id=admin.id,
        email=admin.email,
        name=admin.name,
        last_login_at=admin.last_login_at,
    )
