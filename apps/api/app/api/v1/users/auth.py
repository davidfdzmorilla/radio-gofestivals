from __future__ import annotations

import os
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.deps import RedisDep, SessionDep, SettingsDep, UserDep
from app.core.logging import get_logger
from app.schemas.user import (
    AuthResponse,
    DeleteAccountRequest,
    LoginRequest,
    RegisterRequest,
    UserOut,
)
from app.services import email_verification as verification_service
from app.services import user_auth as auth_service
from app.services.rate_limit import check_rate_limit
from app.services.user_auth import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
)

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.models.user import User

router = APIRouter(prefix="/auth", tags=["user-auth"])
log = get_logger("app.user.auth")

REGISTER_WINDOW = 60 * 60  # límite por settings.register_rate_limit
LOGIN_LIMIT, LOGIN_WINDOW = 5, 60
REFRESH_LIMIT, REFRESH_WINDOW = 30, 60

# Cookie httpOnly con el refresh token (B3): el access JWT vive minutos en
# memoria del cliente; la sesión larga vive aquí, fuera del alcance de XSS.
# path acotado: el navegador solo la envía a los endpoints de auth.
REFRESH_COOKIE = "rgf_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, raw: str, settings: Settings) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=raw,
        max_age=settings.refresh_token_days * 86_400,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=not settings.is_dev,
        samesite="lax",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)


def _to_user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        username=user.username,
        display_name=user.display_name,
        bio=user.bio,
        avatar_url=user.avatar_url,
        is_public=user.is_public,
        email_verified=user.email_verified_at is not None,
        created_at=user.created_at,
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    redis: RedisDep,
    settings: SettingsDep,
) -> AuthResponse:
    ip = request.client.host if request.client else "unknown"
    allowed, _ = await check_rate_limit(
        redis,
        f"user_register:{ip}",
        limit=settings.register_rate_limit,
        window_seconds=REGISTER_WINDOW,
    )
    if not allowed:
        log.warning("user_register_rate_limited", ip=ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate_limit_exceeded",
        )

    try:
        user = await auth_service.register(
            session,
            email=body.email,
            password=body.password,
        )
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="email_already_registered",
        ) from exc

    token, expires_at, raw_refresh = await auth_service.open_session(
        session,
        user,
        settings,
    )
    await session.commit()
    _set_refresh_cookie(response, raw_refresh, settings)
    # Email de verificación best-effort: su fallo no rompe el registro.
    try:
        await verification_service.request_verification(
            session,
            user,
            base_url=os.getenv("PUBLIC_BASE_URL", "https://radio.gofestivals.eu"),
        )
    except Exception:  # noqa: BLE001 — registro nunca debe fallar por el email
        log.warning("verification_request_failed", user_id=str(user.id))
    log.info("user_registered", user_id=str(user.id), email=user.email)
    return AuthResponse(
        user=_to_user_out(user),
        access_token=token,
        expires_at=expires_at,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    redis: RedisDep,
    settings: SettingsDep,
) -> AuthResponse:
    ip = request.client.host if request.client else "unknown"
    allowed, _ = await check_rate_limit(
        redis,
        f"user_login:{ip}",
        limit=LOGIN_LIMIT,
        window_seconds=LOGIN_WINDOW,
    )
    if not allowed:
        log.warning("user_login_rate_limited", ip=ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate_limit_exceeded",
        )

    try:
        user = await auth_service.authenticate(
            session,
            email=body.email,
            password=body.password,
        )
    except InvalidCredentialsError as exc:
        log.warning("user_login_failed", ip=ip, email=body.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_credentials",
        ) from exc

    token, expires_at, raw_refresh = await auth_service.open_session(
        session,
        user,
        settings,
    )
    await session.commit()
    _set_refresh_cookie(response, raw_refresh, settings)
    log.info("user_login_ok", user_id=str(user.id), email=user.email)
    return AuthResponse(
        user=_to_user_out(user),
        access_token=token,
        expires_at=expires_at,
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_session(
    request: Request,
    response: Response,
    session: SessionDep,
    redis: RedisDep,
    settings: SettingsDep,
) -> AuthResponse:
    """Rota el refresh token de la cookie y emite un access token nuevo.

    Un token ya rotado que vuelve a presentarse es señal de robo/replay:
    se revocan todas las sesiones del usuario y se responde 401.
    """
    client_ip = request.client.host if request.client else "unknown"
    allowed, _ = await check_rate_limit(
        redis,
        f"user_refresh:{client_ip}",
        limit=REFRESH_LIMIT,
        window_seconds=REFRESH_WINDOW,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate_limit_exceeded",
        )

    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_refresh_token",
        )
    try:
        user, token, expires_at, new_raw = await auth_service.rotate_session(
            session,
            raw,
            settings,
        )
    except auth_service.RefreshReuseError as exc:
        await session.commit()  # persistir el revoke-all de la detección
        _clear_refresh_cookie(response)
        log.warning("refresh_token_reuse_detected", detail=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_refresh_token",
        ) from exc
    except auth_service.InvalidRefreshError as exc:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_refresh_token",
        ) from exc

    await session.commit()
    _set_refresh_cookie(response, new_raw, settings)
    return AuthResponse(
        user=_to_user_out(user),
        access_token=token,
        expires_at=expires_at,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    session: SessionDep,
) -> None:
    """Revoca el refresh token de la cookie (si lo hay) y la limpia."""
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        await auth_service.close_session(session, raw)
        await session.commit()
    _clear_refresh_cookie(response)


@router.get("/me", response_model=UserOut)
async def me(user: UserDep) -> UserOut:
    return _to_user_out(user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    body: DeleteAccountRequest,
    user: UserDep,
    session: SessionDep,
    response: Response,
) -> None:
    try:
        await auth_service.delete_account(
            session,
            user_id=user.id,
            password=body.password,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_credentials",
        ) from exc

    await session.commit()
    _clear_refresh_cookie(response)
    log.info("user_account_deleted", user_id=str(user.id))
