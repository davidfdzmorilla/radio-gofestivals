from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


async def test_pagination(client: AsyncClient, create_station) -> None:  # type: ignore[no-untyped-def]
    for i in range(25):
        await create_station(slug=f"st-{i:02d}", genre_slugs=["techno"], country_code="ES")

    r = await client.get("/api/v1/stations", params={"page": 1, "size": 10})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 25
    assert data["size"] == 10
    assert data["pages"] == 3
    assert len(data["items"]) == 10

    r2 = await client.get("/api/v1/stations", params={"page": 3, "size": 10})
    assert len(r2.json()["items"]) == 5


async def test_size_above_max_returns_422(client: AsyncClient) -> None:
    r = await client.get("/api/v1/stations", params={"size": 51})
    assert r.status_code == 422


async def test_combined_filters(client: AsyncClient, create_station) -> None:  # type: ignore[no-untyped-def]
    await create_station(slug="es-tek", country_code="ES", curated=True, genre_slugs=["techno"])
    await create_station(slug="fr-tek", country_code="FR", curated=True, genre_slugs=["techno"])
    await create_station(slug="es-house", country_code="ES", curated=True, genre_slugs=["house"])
    await create_station(slug="es-tek-unc", country_code="ES", curated=False, genre_slugs=["techno"])

    r = await client.get(
        "/api/v1/stations",
        params={"country": "ES", "genre": "techno", "curated": "true"},
    )
    assert r.status_code == 200
    slugs = {i["slug"] for i in r.json()["items"]}
    assert slugs == {"es-tek"}


async def test_excludes_non_active(client: AsyncClient, create_station) -> None:  # type: ignore[no-untyped-def]
    await create_station(slug="vivo", status="active")
    await create_station(slug="roto", status="broken")
    await create_station(slug="pend", status="pending")

    r = await client.get("/api/v1/stations")
    slugs = {i["slug"] for i in r.json()["items"]}
    assert slugs == {"vivo"}


async def test_fuzzy_search(client: AsyncClient, create_station) -> None:  # type: ignore[no-untyped-def]
    await create_station(slug="radio-underground", name="Radio Underground")
    await create_station(slug="big-fm", name="Big FM")

    r = await client.get("/api/v1/stations", params={"q": "undergrund"})
    assert r.status_code == 200
    slugs = [i["slug"] for i in r.json()["items"]]
    assert "radio-underground" in slugs
    assert "big-fm" not in slugs


async def test_fuzzy_search_orders_by_similarity(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="techno-exact", name="Techno")
    await create_station(slug="techno-party", name="Techno Party Radio")
    await create_station(slug="neo-tech", name="Neo Tech FM")

    r = await client.get("/api/v1/stations", params={"q": "techno"})
    assert r.status_code == 200
    slugs = [i["slug"] for i in r.json()["items"]]
    assert slugs[0] == "techno-exact"
    assert "techno-party" in slugs
