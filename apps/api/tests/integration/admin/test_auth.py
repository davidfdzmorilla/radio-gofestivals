from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


async def test_login_ok(client: AsyncClient, create_admin) -> None:  # type: ignore[no-untyped-def]
    await create_admin()
    resp = await client.post(
        "/api/v1/admin/auth/login",
        json={"email": "admin@test.com", "password": "supersecret1"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 20
    assert "expires_at" in body


async def test_login_wrong_password(client: AsyncClient, create_admin) -> None:  # type: ignore[no-untyped-def]
    await create_admin()
    resp = await client.post(
        "/api/v1/admin/auth/login",
        json={"email": "admin@test.com", "password": "wrongpass123"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_credentials"


async def test_login_unknown_email(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/admin/auth/login",
        json={"email": "no-such@test.com", "password": "whatever1234"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_credentials"


async def test_login_inactive_admin(client: AsyncClient, create_admin) -> None:  # type: ignore[no-untyped-def]
    await create_admin(email="inactive@test.com", active=False)
    resp = await client.post(
        "/api/v1/admin/auth/login",
        json={"email": "inactive@test.com", "password": "supersecret1"},
    )
    assert resp.status_code == 401


async def test_me_without_token(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/admin/auth/me")
    assert resp.status_code == 401


async def test_me_with_bad_token(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/admin/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"},
    )
    assert resp.status_code == 401


async def test_me_ok(logged_in_client) -> None:  # type: ignore[no-untyped-def]
    resp = await logged_in_client.get("/api/v1/admin/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "admin@test.com"
    assert body["name"] == "Admin Test"
    assert body["last_login_at"] is not None


async def test_login_rate_limit(client: AsyncClient, create_admin) -> None:  # type: ignore[no-untyped-def]
    await create_admin()
    hits_401 = 0
    got_429 = False
    for _ in range(10):
        resp = await client.post(
            "/api/v1/admin/auth/login",
            json={"email": "admin@test.com", "password": "wrongpass"},
        )
        if resp.status_code == 401:
            hits_401 += 1
        elif resp.status_code == 429:
            got_429 = True
            break
    assert hits_401 <= 5
    assert got_429 is True
