from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

REFRESH_COOKIE = "rgf_refresh"


async def _register(client: AsyncClient, email: str = "rt@example.com") -> str:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "supersecret1"},
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["access_token"])


async def test_register_sets_refresh_cookie(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "cookie@example.com", "password": "supersecret1"},
    )
    assert resp.status_code == 201
    cookie = resp.cookies.get(REFRESH_COOKIE)
    assert cookie
    set_cookie = resp.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie
    assert "SameSite=lax" in set_cookie.lower() or "samesite=lax" in set_cookie.lower()


async def test_refresh_rotates_and_old_token_is_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _register(client)
    first_refresh = client.cookies.get(REFRESH_COOKIE)
    assert first_refresh

    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["user"]["email"] == "rt@example.com"
    second_refresh = client.cookies.get(REFRESH_COOKIE)
    assert second_refresh
    assert second_refresh != first_refresh

    # Replay del token ya rotado => 401 y revocación de TODAS las sesiones
    client.cookies.set(REFRESH_COOKIE, first_refresh, path="/api/v1/auth")
    replay = await client.post("/api/v1/auth/refresh")
    assert replay.status_code == 401

    active = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM user_refresh_tokens WHERE revoked_at IS NULL"),
        )
    ).scalar_one()
    assert int(active) == 0

    # La sesión "buena" también quedó revocada por la detección de reuse
    client.cookies.set(REFRESH_COOKIE, second_refresh, path="/api/v1/auth")
    after = await client.post("/api/v1/auth/refresh")
    assert after.status_code == 401


async def test_refresh_without_cookie_401(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


async def test_logout_revokes_and_clears_cookie(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _register(client)
    assert client.cookies.get(REFRESH_COOKIE)

    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 204

    active = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM user_refresh_tokens WHERE revoked_at IS NULL"),
        )
    ).scalar_one()
    assert int(active) == 0

    # La cookie revocada ya no sirve
    again = await client.post("/api/v1/auth/refresh")
    assert again.status_code == 401


async def test_password_reset_revokes_sessions(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _register(client, email="pwreset@example.com")
    await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "pwreset@example.com"},
    )
    token = (
        await db_session.execute(
            text("SELECT token FROM password_reset_tokens ORDER BY created_at DESC LIMIT 1"),
        )
    ).scalar_one()
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": str(token), "new_password": "newpassword1"},
    )
    assert resp.status_code == 200, resp.text

    active = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM user_refresh_tokens WHERE revoked_at IS NULL"),
        )
    ).scalar_one()
    assert int(active) == 0


async def test_access_token_is_short_lived(client: AsyncClient) -> None:
    import jwt as pyjwt

    token = await _register(client, email="short@example.com")
    payload = pyjwt.decode(token, options={"verify_signature": False})
    import time

    ttl = payload["exp"] - time.time()
    assert ttl < 31 * 60  # 30 min de access token, no 30 días
