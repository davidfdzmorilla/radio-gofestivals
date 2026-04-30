from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import RedisDep, SessionDep, SettingsDep, UserDep
from app.core.logging import get_logger
from app.schemas.user import (
    AuthResponse,
    DeleteAccountRequest,
    LoginRequest,
    RegisterRequest,
    UserOut,
)
from app.services import user_auth as auth_service
from app.services.rate_limit import check_rate_limit
from app.services.user_auth import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
)

router = APIRouter(prefix="/auth", tags=["user-auth"])
log = get_logger("app.user.auth")

REGISTER_LIMIT, REGISTER_WINDOW = 3, 60 * 60
LOGIN_LIMIT, LOGIN_WINDOW = 5, 60


def _to_user_out(user) -> UserOut:  # noqa: ANN001
    return UserOut(
        id=user.id,
        email=user.email,
        username=user.username,
        display_name=user.display_name,
        bio=user.bio,
        avatar_url=user.avatar_url,
        is_public=user.is_public,
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
    session: SessionDep,
    redis: RedisDep,
    settings: SettingsDep,
) -> AuthResponse:
    ip = request.client.host if request.client else "unknown"
    allowed, _ = await check_rate_limit(
        redis,
        f"user_register:{ip}",
        limit=REGISTER_LIMIT,
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
            session, email=body.email, password=body.password,
        )
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="email_already_registered",
        ) from exc

    await session.commit()
    token, expires_at = auth_service.mint_token(user, settings)
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
            session, email=body.email, password=body.password,
        )
    except InvalidCredentialsError as exc:
        log.warning("user_login_failed", ip=ip, email=body.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_credentials",
        ) from exc

    token, expires_at = auth_service.mint_token(user, settings)
    log.info("user_login_ok", user_id=str(user.id), email=user.email)
    return AuthResponse(
        user=_to_user_out(user),
        access_token=token,
        expires_at=expires_at,
    )


@router.get("/me", response_model=UserOut)
async def me(user: UserDep) -> UserOut:
    return _to_user_out(user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    body: DeleteAccountRequest,
    user: UserDep,
    session: SessionDep,
) -> None:
    try:
        await auth_service.delete_account(
            session, user_id=user.id, password=body.password,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_credentials",
        ) from exc

    await session.commit()
    log.info("user_account_deleted", user_id=str(user.id))
