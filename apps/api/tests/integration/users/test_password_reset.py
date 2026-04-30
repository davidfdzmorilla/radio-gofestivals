from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from httpx import AsyncClient
    from pytest_mock import MockerFixture
    from sqlalchemy.ext.asyncio import AsyncSession


async def test_forgot_password_user_exists_returns_ok(
    client: AsyncClient,
    db_session: AsyncSession,
    registered_user,  # type: ignore[no-untyped-def]
    mocker: MockerFixture,
) -> None:
    spy = mocker.patch(
        "app.services.password_reset.send_password_reset_email",
        return_value=True,
    )
    await registered_user(email="rp@test.local")

    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "rp@test.local"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    spy.assert_awaited_once()
    # Token row exists
    count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM password_reset_tokens"),
        )
    ).scalar_one()
    assert int(count) == 1


async def test_forgot_password_unknown_email_returns_ok_no_email_sent(
    client: AsyncClient,
    db_session: AsyncSession,
    mocker: MockerFixture,
) -> None:
    spy = mocker.patch(
        "app.services.password_reset.send_password_reset_email",
        return_value=True,
    )
    resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "ghost@test.local"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    spy.assert_not_awaited()
    count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM password_reset_tokens"),
        )
    ).scalar_one()
    assert int(count) == 0


async def test_reset_password_with_valid_token(
    client: AsyncClient,
    db_session: AsyncSession,
    registered_user,  # type: ignore[no-untyped-def]
    mocker: MockerFixture,
) -> None:
    mocker.patch(
        "app.services.password_reset.send_password_reset_email",
        return_value=True,
    )
    user, _ = await registered_user(
        email="cv@test.local", password="oldpass123",
    )
    await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "cv@test.local"},
    )

    token = (
        await db_session.execute(
            text(
                "SELECT token::text FROM password_reset_tokens "
                "WHERE user_id = CAST(:uid AS uuid) ORDER BY created_at DESC LIMIT 1",
            ),
            {"uid": user["id"]},
        )
    ).scalar_one()

    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "newpass1234"},
    )
    assert resp.status_code == 200

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "cv@test.local", "password": "newpass1234"},
    )
    assert login.status_code == 200


async def test_reset_password_token_already_used_400(
    client: AsyncClient,
    db_session: AsyncSession,
    registered_user,  # type: ignore[no-untyped-def]
    mocker: MockerFixture,
) -> None:
    mocker.patch(
        "app.services.password_reset.send_password_reset_email",
        return_value=True,
    )
    user, _ = await registered_user(email="re@test.local")
    await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "re@test.local"},
    )
    token = (
        await db_session.execute(
            text(
                "SELECT token::text FROM password_reset_tokens "
                "WHERE user_id = CAST(:uid AS uuid)",
            ),
            {"uid": user["id"]},
        )
    ).scalar_one()
    r1 = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "newpass1234"},
    )
    assert r1.status_code == 200
    r2 = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "anotherpw123"},
    )
    assert r2.status_code == 400


async def test_reset_password_expired_token_400(
    client: AsyncClient,
    db_session: AsyncSession,
    registered_user,  # type: ignore[no-untyped-def]
) -> None:
    user, _ = await registered_user(email="exp@test.local")
    expired_token = (
        await db_session.execute(
            text(
                """
                INSERT INTO password_reset_tokens (user_id, expires_at)
                VALUES (CAST(:uid AS uuid), :exp)
                RETURNING token::text
                """,
            ),
            {
                "uid": user["id"],
                "exp": datetime.now(tz=UTC) - timedelta(hours=1),
            },
        )
    ).scalar_one()
    await db_session.commit()
    resp = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": expired_token, "new_password": "newpass1234"},
    )
    assert resp.status_code == 400
