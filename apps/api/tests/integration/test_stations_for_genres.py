from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

URL = "/api/v1/stations/for-genres"


async def test_ranks_by_number_of_genres_covered(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="only-techno", quality_score=95, genre_slugs=["techno"])
    await create_station(slug="both", quality_score=10, genre_slugs=["techno", "house"])
    await create_station(slug="only-house", quality_score=90, genre_slugs=["house"])
    await create_station(slug="trance-only", quality_score=99, genre_slugs=["trance"])

    r = await client.get(URL, params={"genres": "techno,house"})
    assert r.status_code == 200
    slugs = [i["slug"] for i in r.json()["items"]]
    assert slugs[0] == "both"
    assert set(slugs) == {"both", "only-techno", "only-house"}


async def test_excludes_broken_and_hidden(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="ok", genre_slugs=["techno"])
    await create_station(slug="broken", status="broken", genre_slugs=["techno"])
    await create_station(slug="hidden", genre_slugs=["techno"])
    await db_session.execute(text("UPDATE stations SET hidden = true WHERE slug = 'hidden'"))
    await db_session.commit()

    r = await client.get(URL, params={"genres": "techno"})
    assert [i["slug"] for i in r.json()["items"]] == ["ok"]


async def test_limit_is_respected_and_capped(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    for i in range(5):
        await create_station(slug=f"t-{i}", genre_slugs=["techno"])
    r = await client.get(URL, params={"genres": "techno", "limit": 2})
    assert len(r.json()["items"]) == 2
    r = await client.get(URL, params={"genres": "techno", "limit": 13})
    assert r.status_code == 422


async def test_order_of_genres_does_not_matter(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="a", genre_slugs=["techno", "house"])
    r1 = await client.get(URL, params={"genres": "techno,house"})
    r2 = await client.get(URL, params={"genres": "house, TECHNO,house"})
    assert r1.json() == r2.json()


async def test_unknown_genre_returns_empty_list(client: AsyncClient) -> None:
    r = await client.get(URL, params={"genres": "no-such-genre"})
    assert r.status_code == 200
    assert r.json()["items"] == []


async def test_invalid_genres_return_422(client: AsyncClient) -> None:
    for bad in ["", ",,", "te chno", "techno;drop", "x" * 51, ",".join(f"g{i}" for i in range(31))]:
        r = await client.get(URL, params={"genres": bad})
        assert r.status_code == 422, bad
    assert (await client.get(URL)).status_code == 422
