from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def test_featured_size_above_max_returns_422(client: AsyncClient) -> None:
    r = await client.get("/api/v1/stations/featured", params={"size": 25})
    assert r.status_code == 422


async def test_featured_returns_only_curated_active_visible(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="cur-visible", curated=True, genre_slugs=["techno"])
    await create_station(slug="cur-broken", curated=True, status="broken", genre_slugs=["techno"])
    await create_station(slug="not-curated", curated=False, genre_slugs=["techno"])

    r = await client.get("/api/v1/stations/featured", params={"size": 12})
    assert r.status_code == 200
    slugs = {i["slug"] for i in r.json()["items"]}
    assert slugs == {"cur-visible"}


async def test_featured_caps_two_per_primary_genre(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    # 5 techno, 3 house, 1 trance — all curated/active. Quality scores chosen
    # so the natural ordering would surface 5 techno before any house.
    for i in range(5):
        await create_station(
            slug=f"techno-{i}",
            curated=True,
            quality_score=90 - i,
            genre_slugs=["techno"],
        )
    for i in range(3):
        await create_station(
            slug=f"house-{i}",
            curated=True,
            quality_score=80 - i,
            genre_slugs=["house"],
        )
    await create_station(
        slug="trance-0",
        curated=True,
        quality_score=70,
        genre_slugs=["trance"],
    )

    r = await client.get("/api/v1/stations/featured", params={"size": 12})
    assert r.status_code == 200
    items = r.json()["items"]
    by_genre: dict[str, int] = {}
    for item in items:
        # Each station's first genre slug is its only genre in this fixture.
        primary = item["genres"][0]
        by_genre[primary] = by_genre.get(primary, 0) + 1
    for genre, n in by_genre.items():
        assert n <= 2, f"genre {genre} appeared {n} times, cap is 2"
    # Order: 2 techno first (highest qs), then 2 house, then trance.
    slugs = [i["slug"] for i in items]
    assert slugs == ["techno-0", "techno-1", "house-0", "house-1", "trance-0"]


async def test_featured_skips_stations_with_no_genres(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="orphan", curated=True, quality_score=99, genre_slugs=None)
    await create_station(slug="tagged", curated=True, quality_score=50, genre_slugs=["techno"])

    r = await client.get("/api/v1/stations/featured", params={"size": 12})
    slugs = [i["slug"] for i in r.json()["items"]]
    assert "orphan" not in slugs
    assert "tagged" in slugs


async def test_featured_excludes_hidden(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="visible", curated=True, genre_slugs=["techno"])
    await create_station(slug="hidden", curated=True, genre_slugs=["techno"])

    await db_session.execute(
        text("UPDATE stations SET hidden = true WHERE slug = 'hidden'"),
    )
    await db_session.commit()

    r = await client.get("/api/v1/stations/featured", params={"size": 12})
    slugs = {i["slug"] for i in r.json()["items"]}
    assert "visible" in slugs
    assert "hidden" not in slugs
