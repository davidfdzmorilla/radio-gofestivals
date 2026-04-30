from __future__ import annotations

from typing import TYPE_CHECKING

from tests.integration.admin.test_stations_list import _seed_station

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def test_list_without_auth_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/favorites")
    assert resp.status_code == 401


async def test_add_then_list_favorites(
    client: AsyncClient,
    db_session: AsyncSession,
    registered_user,  # type: ignore[no-untyped-def]
) -> None:
    _, token = await registered_user()
    sid = await _seed_station(db_session, slug="fav-1")
    headers = {"Authorization": f"Bearer {token}"}
    add = await client.post(
        f"/api/v1/favorites/{sid}", headers=headers,
    )
    assert add.status_code == 201
    listing = await client.get("/api/v1/favorites", headers=headers)
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 1
    assert body["items"][0]["slug"] == "fav-1"


async def test_add_favorite_idempotent(
    client: AsyncClient,
    db_session: AsyncSession,
    registered_user,  # type: ignore[no-untyped-def]
) -> None:
    _, token = await registered_user()
    sid = await _seed_station(db_session, slug="fav-idem")
    headers = {"Authorization": f"Bearer {token}"}
    r1 = await client.post(
        f"/api/v1/favorites/{sid}", headers=headers,
    )
    r2 = await client.post(
        f"/api/v1/favorites/{sid}", headers=headers,
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    listing = await client.get("/api/v1/favorites", headers=headers)
    assert listing.json()["total"] == 1


async def test_remove_favorite(
    client: AsyncClient,
    db_session: AsyncSession,
    registered_user,  # type: ignore[no-untyped-def]
) -> None:
    _, token = await registered_user()
    sid = await _seed_station(db_session, slug="fav-rm")
    headers = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/favorites/{sid}", headers=headers)
    rm = await client.delete(
        f"/api/v1/favorites/{sid}", headers=headers,
    )
    assert rm.status_code == 204
    listing = await client.get("/api/v1/favorites", headers=headers)
    assert listing.json()["total"] == 0


async def test_add_favorite_unknown_station_404(
    client: AsyncClient,
    registered_user,  # type: ignore[no-untyped-def]
) -> None:
    _, token = await registered_user()
    fake = "00000000-0000-0000-0000-000000000000"
    resp = await client.post(
        f"/api/v1/favorites/{fake}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


async def test_migrate_favorites_counts(
    client: AsyncClient,
    db_session: AsyncSession,
    registered_user,  # type: ignore[no-untyped-def]
) -> None:
    _, token = await registered_user()
    a = await _seed_station(db_session, slug="mig-a")
    b = await _seed_station(db_session, slug="mig-b")
    c = await _seed_station(db_session, slug="mig-c")
    headers = {"Authorization": f"Bearer {token}"}
    # Pre-add `a` so it counts as already_existed.
    await client.post(f"/api/v1/favorites/{a}", headers=headers)

    fake = "00000000-0000-0000-0000-000000000099"
    resp = await client.post(
        "/api/v1/favorites/migrate",
        json={"station_ids": [str(a), str(b), str(c), fake]},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["added"] == 2
    assert body["already_existed"] == 1
    assert body["invalid"] == 1
