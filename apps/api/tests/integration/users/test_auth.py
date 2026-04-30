from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def test_register_returns_201_with_token(
    client: AsyncClient,
) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "new@test.local", "password": "supersecret1"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["user"]["email"] == "new@test.local"
    assert len(body["access_token"]) > 20


async def test_register_duplicate_email_400(
    client: AsyncClient,
) -> None:
    payload = {"email": "dup@test.local", "password": "supersecret1"}
    r1 = await client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 400
    assert r2.json()["detail"] == "email_already_registered"


async def test_register_password_too_short_422(
    client: AsyncClient,
) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "short@test.local", "password": "tiny"},
    )
    assert resp.status_code == 422


async def test_login_ok(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "li@test.local", "password": "supersecret1"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "li@test.local", "password": "supersecret1"},
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["email"] == "li@test.local"


async def test_login_wrong_password_401(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"email": "wp@test.local", "password": "supersecret1"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "wp@test.local", "password": "WRONG"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_credentials"


async def test_me_without_token_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_with_token(
    client: AsyncClient, registered_user,  # type: ignore[no-untyped-def]
) -> None:
    user, token = await registered_user(email="me@test.local")
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@test.local"


async def test_delete_me_with_correct_password(
    client: AsyncClient,
    registered_user,  # type: ignore[no-untyped-def]
    db_session: AsyncSession,
) -> None:
    _, token = await registered_user(email="del@test.local")
    resp = await client.request(
        "DELETE",
        "/api/v1/auth/me",
        json={"password": "testpass123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    row = (
        await db_session.execute(
            text(
                "SELECT email, deleted_at FROM users "
                "WHERE email LIKE 'deleted_%@deleted.local'",
            ),
        )
    ).first()
    assert row is not None
    assert row[1] is not None


async def test_delete_me_wrong_password_401(
    client: AsyncClient,
    registered_user,  # type: ignore[no-untyped-def]
) -> None:
    _, token = await registered_user(email="dw@test.local")
    resp = await client.request(
        "DELETE",
        "/api/v1/auth/me",
        json={"password": "WRONG"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


async def test_admin_token_cannot_act_as_user(
    client: AsyncClient,
) -> None:
    """Cross-audience defense: admin tokens carry no aud='user' so the
    user decoder must reject them outright."""
    from app.core.config import get_settings
    from app.core.security import issue_access_token
    import uuid

    settings = get_settings()
    token, _ = issue_access_token(uuid.uuid4(), "admin@x.com", settings)
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401
