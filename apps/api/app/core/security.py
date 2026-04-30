from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import Settings
from app.core.logging import get_logger

_log = get_logger("security")

BCRYPT_MAX_BYTES = 72


def _prep(plain: str) -> bytes:
    return plain.encode("utf-8")[:BCRYPT_MAX_BYTES]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_prep(plain), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bool(bcrypt.checkpw(_prep(plain), hashed.encode("utf-8")))
    except (ValueError, TypeError):
        _log.warning("password_verify_malformed_hash")
        return False


def issue_access_token(
    admin_id: uuid.UUID,
    email: str,
    settings: Settings,
) -> tuple[str, datetime]:
    expire = datetime.now(tz=UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(admin_id),
        "email": email,
        "exp": int(expire.timestamp()),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return token, expire


class TokenError(Exception):
    pass


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError as exc:
        msg = "token_expired"
        raise TokenError(msg) from exc
    except jwt.InvalidTokenError as exc:
        msg = "invalid_token"
        raise TokenError(msg) from exc


# 30 days for end-user accounts (admin uses 24h via jwt_expire_minutes).
USER_TOKEN_TTL_DAYS = 30


def issue_user_token(
    user_id: uuid.UUID,
    email: str,
    settings: Settings,
) -> tuple[str, datetime]:
    """Mint a 30d JWT for an end user. Audience='user' separates them from
    admin tokens (which carry no audience claim — verified via DB lookup).
    """
    expire = datetime.now(tz=UTC) + timedelta(days=USER_TOKEN_TTL_DAYS)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "aud": "user",
        "exp": int(expire.timestamp()),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return token, expire


def decode_user_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            audience="user",
        )
    except jwt.ExpiredSignatureError as exc:
        msg = "token_expired"
        raise TokenError(msg) from exc
    except jwt.InvalidAudienceError as exc:
        msg = "wrong_audience"
        raise TokenError(msg) from exc
    except jwt.InvalidTokenError as exc:
        msg = "invalid_token"
        raise TokenError(msg) from exc
