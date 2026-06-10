from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.security import (
    hash_password,
    hash_refresh_token,
    issue_user_token,
    make_refresh_token,
    verify_password,
)
from app.repos import user_refresh_tokens as refresh_repo
from app.repos import users as users_repo

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.config import Settings
    from app.models.user import User


class EmailAlreadyRegisteredError(Exception):
    """Raised when register() is called with an email already in use."""


class InvalidCredentialsError(Exception):
    """Raised by authenticate() when email or password do not match."""


class InvalidRefreshError(Exception):
    """Refresh token desconocido, caducado o de usuario inexistente."""


class RefreshReuseError(Exception):
    """Replay de un token ya rotado: todas las sesiones quedan revocadas."""


async def register(
    session: AsyncSession,
    *,
    email: str,
    password: str,
) -> User:
    existing = await users_repo.get_user_by_email(session, email)
    if existing is not None:
        raise EmailAlreadyRegisteredError(email)
    return await users_repo.create_user(
        session,
        email=email,
        password_hash=hash_password(password),
    )


async def authenticate(
    session: AsyncSession,
    *,
    email: str,
    password: str,
) -> User:
    user = await users_repo.get_user_by_email(session, email)
    if user is None:
        raise InvalidCredentialsError
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError
    return user


def mint_token(
    user: User,
    settings: Settings,
) -> tuple[str, datetime]:
    return issue_user_token(user.id, user.email, settings)


async def open_session(
    session: AsyncSession,
    user: User,
    settings: Settings,
) -> tuple[str, datetime, str]:
    """(access_token, expira, refresh en claro) — el caller setea la cookie."""
    token, expires_at = issue_user_token(user.id, user.email, settings)
    raw, token_hash = make_refresh_token()
    await refresh_repo.create(
        session,
        token_hash=token_hash,
        user_id=user.id,
        ttl_days=settings.refresh_token_days,
    )
    return token, expires_at, raw


async def rotate_session(
    session: AsyncSession,
    raw_refresh: str,
    settings: Settings,
) -> tuple[User, str, datetime, str]:
    """Valida y rota el refresh token; (user, access, expira, refresh nuevo).

    El replay de un token revocado dispara el cierre de TODAS las sesiones
    del usuario antes de fallar — el atacante y la víctima pierden la
    sesión, y la víctima se re-autentica con password.
    """
    old_hash = hash_refresh_token(raw_refresh)
    state = await refresh_repo.get_state(session, old_hash)
    if state is None:
        raise InvalidRefreshError("unknown_token")
    user_id, valid, revoked = state
    if revoked:
        await refresh_repo.revoke_all_for_user(session, user_id)
        raise RefreshReuseError(f"user={user_id}")
    if not valid:
        raise InvalidRefreshError("expired_token")

    user = await users_repo.get_user_by_id(session, user_id)
    if user is None:
        raise InvalidRefreshError("user_gone")

    token, expires_at = issue_user_token(user.id, user.email, settings)
    new_raw, new_hash = make_refresh_token()
    await refresh_repo.rotate(
        session,
        old_hash=old_hash,
        new_hash=new_hash,
        user_id=user.id,
        ttl_days=settings.refresh_token_days,
    )
    return user, token, expires_at, new_raw


async def close_session(session: AsyncSession, raw_refresh: str) -> None:
    await refresh_repo.revoke(session, hash_refresh_token(raw_refresh))


async def delete_account(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    password: str,
) -> bool:
    """Verify the password and soft-delete the account.

    The reauth-with-password requirement adds defense in depth: a stolen
    JWT can't nuke the account by itself.
    """
    user = await users_repo.get_user_by_id(session, user_id)
    if user is None:
        return False
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError
    await users_repo.soft_delete(session, user_id)
    await refresh_repo.revoke_all_for_user(session, user_id)
    return True
