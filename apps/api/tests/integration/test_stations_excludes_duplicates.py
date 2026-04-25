from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


async def test_list_stations_excludes_duplicates(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="sub-fm-keep", name="Sub FM", status="active")
    await create_station(slug="sub-fm-dup", name="Sub FM", status="duplicate")

    resp = await client.get("/api/v1/stations")
    assert resp.status_code == 200
    payload = resp.json()
    slugs = [s["slug"] for s in payload["items"]]
    assert "sub-fm-keep" in slugs
    assert "sub-fm-dup" not in slugs
    assert payload["total"] == 1


async def test_station_detail_returns_404_for_duplicate(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="hidden-dup", status="duplicate")
    resp = await client.get("/api/v1/stations/hidden-dup")
    assert resp.status_code == 404


async def test_genres_count_excludes_duplicates(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="tek-active", genre_slugs=["techno"], status="active")
    await create_station(slug="tek-dup", genre_slugs=["techno"], status="duplicate")

    resp = await client.get("/api/v1/genres")
    assert resp.status_code == 200
    techno = next(g for g in resp.json() if g["slug"] == "techno")
    assert techno["station_count"] == 1
