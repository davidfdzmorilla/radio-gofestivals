from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def test_401_without_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/admin/stations/pending")
    assert resp.status_code == 401


async def test_lists_pending_ordered(
    logged_in_client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
    db_session: AsyncSession,
) -> None:
    await create_station(slug="p-lo", status="pending", quality_score=30)
    await create_station(slug="p-hi", status="pending", quality_score=90)
    await create_station(slug="active", status="active")

    tek_id = (
        await db_session.execute(text("SELECT id FROM stations WHERE slug='p-hi'"))
    ).scalar_one()
    await db_session.execute(
        text(
            """
            INSERT INTO station_genres (station_id, genre_id, source, confidence)
            SELECT :sid, id, 'rb_tag', 60 FROM genres WHERE slug='techno'
            """,
        ),
        {"sid": tek_id},
    )
    await db_session.commit()

    resp = await logged_in_client.get("/api/v1/admin/stations/pending")
    assert resp.status_code == 200
    body = resp.json()
    slugs = [i["slug"] for i in body["items"]]
    assert slugs == ["p-hi", "p-lo"]
    assert body["total"] == 2

    hi = body["items"][0]
    assert hi["genres"][0]["slug"] == "techno"
    assert hi["genres"][0]["confidence"] == 60


async def test_filter_by_country(
    logged_in_client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="es-p", status="pending", country_code="ES")
    await create_station(slug="fr-p", status="pending", country_code="FR")

    resp = await logged_in_client.get(
        "/api/v1/admin/stations/pending", params={"country": "ES"},
    )
    assert resp.status_code == 200
    slugs = [i["slug"] for i in resp.json()["items"]]
    assert slugs == ["es-p"]


async def test_filter_has_geo(
    logged_in_client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="geo", status="pending", lat=40.4, lng=-3.7)
    await create_station(slug="nogeo", status="pending")

    resp = await logged_in_client.get(
        "/api/v1/admin/stations/pending", params={"has_geo": "true"},
    )
    slugs = [i["slug"] for i in resp.json()["items"]]
    assert slugs == ["geo"]


async def test_pagination(
    logged_in_client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    for i in range(15):
        await create_station(slug=f"p-{i:02d}", status="pending", quality_score=50)

    resp = await logged_in_client.get(
        "/api/v1/admin/stations/pending", params={"size": 10, "page": 2},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 15
    assert body["pages"] == 2
    assert len(body["items"]) == 5
