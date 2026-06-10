from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def _register(client: AsyncClient, email: str = "verify@example.com") -> str:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "supersecret1"},
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["access_token"])


async def _latest_token(db_session: AsyncSession) -> uuid.UUID:
    token = (
        await db_session.execute(
            text(
                "SELECT token FROM email_verification_tokens ORDER BY created_at DESC LIMIT 1",
            ),
        )
    ).scalar_one()
    return uuid.UUID(str(token))


async def test_register_creates_verification_token_and_flag_false(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "fresh@example.com", "password": "supersecret1"},
    )
    assert resp.status_code == 201
    assert resp.json()["user"]["email_verified"] is False

    count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM email_verification_tokens"),
        )
    ).scalar_one()
    assert int(count) == 1


async def test_verify_email_sets_flag(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token_header = await _register(client)
    token = await _latest_token(db_session)

    resp = await client.post(
        "/api/v1/auth/verify-email",
        json={"token": str(token)},
    )
    assert resp.status_code == 200

    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token_header}"},
    )
    assert me.json()["email_verified"] is True

    verified_at = (
        await db_session.execute(
            text("SELECT email_verified_at FROM users WHERE email = 'verify@example.com'"),
        )
    ).scalar_one()
    assert verified_at is not None


async def test_verify_token_single_use_and_unknown_400(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _register(client)
    token = await _latest_token(db_session)

    first = await client.post("/api/v1/auth/verify-email", json={"token": str(token)})
    assert first.status_code == 200
    second = await client.post("/api/v1/auth/verify-email", json={"token": str(token)})
    assert second.status_code == 400

    unknown = await client.post(
        "/api/v1/auth/verify-email",
        json={"token": str(uuid.uuid4())},
    )
    assert unknown.status_code == 400


async def test_resend_creates_new_token_and_noop_when_verified(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    access = await _register(client)
    headers = {"Authorization": f"Bearer {access}"}

    resend = await client.post("/api/v1/auth/resend-verification", headers=headers)
    assert resend.status_code == 200
    count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM email_verification_tokens"),
        )
    ).scalar_one()
    assert int(count) == 2  # el del registro + el reenviado

    token = await _latest_token(db_session)
    await client.post("/api/v1/auth/verify-email", json={"token": str(token)})

    after_verified = await client.post(
        "/api/v1/auth/resend-verification",
        headers=headers,
    )
    assert after_verified.status_code == 200
    assert after_verified.json()["sent"] is False  # ya verificado: no-op

    final_count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM email_verification_tokens"),
        )
    ).scalar_one()
    assert int(final_count) == 2  # sin token nuevo
