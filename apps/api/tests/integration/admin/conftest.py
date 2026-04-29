from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest_asyncio
from sqlalchemy import text

from app.core.security import hash_password

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture(autouse=True)
async def _reset_admin_tables(db_session: AsyncSession) -> AsyncIterator[None]:
    await db_session.execute(
        text(
            "TRUNCATE admin_jobs, curation_log, admins RESTART IDENTITY CASCADE",
        ),
    )
    await db_session.commit()
    yield


@pytest_asyncio.fixture
async def create_admin(db_session: AsyncSession):  # type: ignore[no-untyped-def]
    async def _make(
        email: str = "admin@test.com",
        password: str = "supersecret1",
        name: str = "Admin Test",
        active: bool = True,
    ) -> uuid.UUID:
        ph = hash_password(password)
        result = await db_session.execute(
            text(
                """
                INSERT INTO admins (email, password_hash, name, active)
                VALUES (:email, :ph, :name, :active)
                RETURNING id
                """,
            ),
            {"email": email.lower(), "ph": ph, "name": name, "active": active},
        )
        await db_session.commit()
        return uuid.UUID(str(result.scalar_one()))

    return _make


@pytest_asyncio.fixture
async def logged_in_client(client, create_admin):  # type: ignore[no-untyped-def]
    await create_admin()
    resp = await client.post(
        "/api/v1/admin/auth/login",
        json={"email": "admin@test.com", "password": "supersecret1"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
