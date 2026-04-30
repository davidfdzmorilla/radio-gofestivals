from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

from tests.integration.admin.test_stations_list import _seed_station

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def test_like_without_auth_401(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    sid = await _seed_station(db_session, slug="lk-anon")
    resp = await client.post(f"/api/v1/stations/{sid}/like")
    assert resp.status_code == 401


async def test_like_first_time_increments_counter(
    client: AsyncClient,
    db_session: AsyncSession,
    registered_user,  # type: ignore[no-untyped-def]
) -> None:
    _, token = await registered_user()
    sid = await _seed_station(db_session, slug="lk-1")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        f"/api/v1/stations/{sid}/like", headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user_voted"] is True
    assert body["votes_local"] == 1


async def test_like_idempotent(
    client: AsyncClient,
    db_session: AsyncSession,
    registered_user,  # type: ignore[no-untyped-def]
) -> None:
    _, token = await registered_user()
    sid = await _seed_station(db_session, slug="lk-idem")
    headers = {"Authorization": f"Bearer {token}"}
    r1 = await client.post(
        f"/api/v1/stations/{sid}/like", headers=headers,
    )
    r2 = await client.post(
        f"/api/v1/stations/{sid}/like", headers=headers,
    )
    assert r1.json()["votes_local"] == 1
    assert r2.json()["votes_local"] == 1


async def test_unlike_decrements(
    client: AsyncClient,
    db_session: AsyncSession,
    registered_user,  # type: ignore[no-untyped-def]
) -> None:
    _, token = await registered_user()
    sid = await _seed_station(db_session, slug="lk-rm")
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/stations/{sid}/like", headers=headers)
    rm = await client.delete(
        f"/api/v1/stations/{sid}/like", headers=headers,
    )
    assert rm.status_code == 200
    body = rm.json()
    assert body["user_voted"] is False
    assert body["votes_local"] == 0


async def test_unlike_never_voted_is_safe(
    client: AsyncClient,
    db_session: AsyncSession,
    registered_user,  # type: ignore[no-untyped-def]
) -> None:
    _, token = await registered_user()
    sid = await _seed_station(db_session, slug="lk-never")
    headers = {"Authorization": f"Bearer {token}"}
    rm = await client.delete(
        f"/api/v1/stations/{sid}/like", headers=headers,
    )
    assert rm.status_code == 200
    assert rm.json()["votes_local"] == 0


async def test_two_users_independent_counter(
    client: AsyncClient,
    db_session: AsyncSession,
    registered_user,  # type: ignore[no-untyped-def]
) -> None:
    _, token_a = await registered_user(email="a@test.local")
    _, token_b = await registered_user(email="b@test.local")
    sid = await _seed_station(db_session, slug="lk-two")
    await client.post(
        f"/api/v1/stations/{sid}/like",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    resp = await client.post(
        f"/api/v1/stations/{sid}/like",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.json()["votes_local"] == 2
    count = (
        await db_session.execute(
            text(
                "SELECT votes_local FROM stations WHERE id = CAST(:s AS uuid)",
            ),
            {"s": str(sid)},
        )
    ).scalar_one()
    assert int(count) == 2
