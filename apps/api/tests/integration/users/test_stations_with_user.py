from __future__ import annotations

from typing import TYPE_CHECKING

from tests.integration.admin.test_stations_list import _seed_station

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def test_list_anon_omits_personal_fields(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    await _seed_station(db_session, slug="anon-1", status="active")
    resp = await client.get("/api/v1/stations")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(it["slug"] == "anon-1" for it in items)
    target = next(it for it in items if it["slug"] == "anon-1")
    assert target["is_favorite"] is None
    assert target["user_voted"] is None


async def test_list_with_user_includes_personal_fields(
    client: AsyncClient,
    db_session: AsyncSession,
    registered_user,  # type: ignore[no-untyped-def]
) -> None:
    sid = await _seed_station(db_session, slug="usr-1", status="active")
    _, token = await registered_user()
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/favorites/{sid}", headers=headers)
    await client.post(f"/api/v1/stations/{sid}/like", headers=headers)

    resp = await client.get("/api/v1/stations", headers=headers)
    items = resp.json()["items"]
    target = next(it for it in items if it["slug"] == "usr-1")
    assert target["is_favorite"] is True
    assert target["user_voted"] is True
    assert target["votes_local"] == 1


async def test_detail_with_user_personalizes_without_polluting_cache(
    client: AsyncClient,
    db_session: AsyncSession,
    registered_user,  # type: ignore[no-untyped-def]
) -> None:
    sid = await _seed_station(db_session, slug="det-usr", status="active")
    _, token = await registered_user()
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/favorites/{sid}", headers=headers)

    # First fetch with user → personalised
    r_user = await client.get(
        "/api/v1/stations/det-usr", headers=headers,
    )
    assert r_user.status_code == 200
    assert r_user.json()["is_favorite"] is True

    # Anonymous fetch must NOT see the previous user's flag
    r_anon = await client.get("/api/v1/stations/det-usr")
    assert r_anon.status_code == 200
    assert r_anon.json()["is_favorite"] is None
