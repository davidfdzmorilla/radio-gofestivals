from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

from app.services import genres as genres_service

if TYPE_CHECKING:
    from httpx import AsyncClient
    from pytest_mock import MockerFixture
    from sqlalchemy.ext.asyncio import AsyncSession


async def test_401_without_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/admin/genres",
        json={"slug": "dummy", "name": "Dummy"},
    )
    assert resp.status_code == 401


async def test_post_create_and_409_on_duplicate(
    logged_in_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    resp = await logged_in_client.post(
        "/api/v1/admin/genres",
        json={"slug": "acid", "name": "Acid", "sort_order": 15},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "acid"

    exists = (
        await db_session.execute(text("SELECT COUNT(*) FROM genres WHERE slug='acid'"))
    ).scalar_one()
    assert exists == 1

    dup = await logged_in_client.post(
        "/api/v1/admin/genres",
        json={"slug": "acid", "name": "Acid dup"},
    )
    assert dup.status_code == 409


async def test_put_partial_update(
    logged_in_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    create = await logged_in_client.post(
        "/api/v1/admin/genres", json={"slug": "uk-garage", "name": "UK Garage"},
    )
    gid = create.json()["id"]

    resp = await logged_in_client.put(
        f"/api/v1/admin/genres/{gid}",
        json={"color_hex": "#ABCDEF"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["color_hex"] == "#ABCDEF"
    assert body["slug"] == "uk-garage"


async def test_put_404_missing(logged_in_client: AsyncClient) -> None:
    resp = await logged_in_client.put(
        "/api/v1/admin/genres/9999", json={"name": "Nope"},
    )
    assert resp.status_code == 404


async def test_delete_blocked_when_in_use(
    logged_in_client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
    db_session: AsyncSession,
) -> None:
    await create_station(slug="s", status="active", genre_slugs=["techno"])
    tek_id = (
        await db_session.execute(text("SELECT id FROM genres WHERE slug='techno'"))
    ).scalar_one()

    resp = await logged_in_client.delete(f"/api/v1/admin/genres/{tek_id}")
    assert resp.status_code == 409


async def test_delete_unused_ok(
    logged_in_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    create = await logged_in_client.post(
        "/api/v1/admin/genres", json={"slug": "chiptune", "name": "Chiptune"},
    )
    gid = create.json()["id"]
    resp = await logged_in_client.delete(f"/api/v1/admin/genres/{gid}")
    assert resp.status_code == 204
    exists = (
        await db_session.execute(text("SELECT COUNT(*) FROM genres WHERE id=:id"), {"id": gid})
    ).scalar_one()
    assert exists == 0


async def test_crud_invalidates_cache(
    logged_in_client: AsyncClient,
    mocker: MockerFixture,
) -> None:
    spy = mocker.spy(genres_service, "fetch_genres_with_counts")
    await logged_in_client.get("/api/v1/genres")
    assert spy.call_count == 1
    await logged_in_client.get("/api/v1/genres")
    assert spy.call_count == 1

    await logged_in_client.post(
        "/api/v1/admin/genres", json={"slug": "leftfield", "name": "Leftfield"},
    )

    await logged_in_client.get("/api/v1/genres")
    assert spy.call_count == 2
