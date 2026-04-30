from __future__ import annotations

from typing import TYPE_CHECKING

import pytest_asyncio
from sqlalchemy import text

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture(autouse=True)
async def _reset_user_tables(db_session: AsyncSession) -> AsyncIterator[None]:
    await db_session.execute(
        text(
            "TRUNCATE password_reset_tokens, user_votes, user_favorites, "
            "users RESTART IDENTITY CASCADE",
        ),
    )
    await db_session.commit()
    yield


@pytest_asyncio.fixture
async def registered_user(client: AsyncClient):  # type: ignore[no-untyped-def]
    """Register a fresh user and return (user_dict, token).

    Uses the public endpoint so the test exercises the same code path
    the frontend will hit. Each call creates a new email to avoid
    collisions when tests use this fixture multiple times.
    """
    counter = {"n": 0}

    async def _make(
        email: str | None = None, password: str = "testpass123",
    ) -> tuple[dict, str]:
        if email is None:
            counter["n"] += 1
            email = f"user{counter['n']}@test.local"
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        return body["user"], body["access_token"]

    return _make
