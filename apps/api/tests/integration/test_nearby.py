from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


MADRID = (40.4168, -3.7038)
VALENCIA = (39.4699, -0.3763)
SEVILLE = (37.3891, -5.9845)
BERLIN = (52.52, 13.405)


async def test_nearby_returns_within_radius_sorted(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="s-mad", lat=MADRID[0], lng=MADRID[1])
    await create_station(slug="s-val", lat=VALENCIA[0], lng=VALENCIA[1])
    await create_station(slug="s-sev", lat=SEVILLE[0], lng=SEVILLE[1])
    await create_station(slug="s-ber", lat=BERLIN[0], lng=BERLIN[1])

    r = await client.get(
        "/api/v1/stations/nearby",
        params={"lat": MADRID[0], "lng": MADRID[1], "radius_km": 450},
    )
    assert r.status_code == 200, r.text
    items = r.json()
    slugs = [i["slug"] for i in items]

    assert "s-mad" in slugs
    assert "s-val" in slugs
    assert "s-sev" in slugs
    assert "s-ber" not in slugs

    distances = [i["distance_km"] for i in items]
    assert distances == sorted(distances)
    assert slugs[0] == "s-mad"
    assert items[0]["distance_km"] < 1


async def test_nearby_rejects_invalid_coords(client: AsyncClient) -> None:
    r = await client.get("/api/v1/stations/nearby", params={"lat": 99, "lng": 0})
    assert r.status_code == 422


async def test_nearby_rejects_radius_above_max(client: AsyncClient) -> None:
    r = await client.get(
        "/api/v1/stations/nearby",
        params={"lat": 0, "lng": 0, "radius_km": 501},
    )
    assert r.status_code == 422
