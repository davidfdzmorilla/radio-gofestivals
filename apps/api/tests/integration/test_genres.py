from __future__ import annotations

import os
from typing import TYPE_CHECKING

from redis.asyncio import Redis

from app.services import genres as genres_service

if TYPE_CHECKING:
    from httpx import AsyncClient
    from pytest_mock import MockerFixture


async def test_genres_tree_structure(client: AsyncClient, create_station) -> None:  # type: ignore[no-untyped-def]
    await create_station(slug="tek-1", genre_slugs=["techno"])
    await create_station(slug="tek-2", genre_slugs=["minimal"])
    await create_station(slug="hs-1", genre_slugs=["deep-house"])

    resp = await client.get("/api/v1/genres")
    assert resp.status_code == 200
    tree = resp.json()

    roots = {g["slug"]: g for g in tree}
    assert "techno" in roots
    assert "house" in roots

    techno = roots["techno"]
    minimal_children = [c for c in techno["children"] if c["slug"] == "minimal"]
    assert len(minimal_children) == 1
    assert minimal_children[0]["station_count"] == 1
    assert techno["station_count"] == 1

    house = roots["house"]
    deep = [c for c in house["children"] if c["slug"] == "deep-house"]
    assert deep[0]["station_count"] == 1


async def test_genres_cache_hit_skips_repo(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
    mocker: MockerFixture,
) -> None:
    spy = mocker.spy(genres_service, "fetch_genres_with_counts")

    await create_station(slug="cached-1", genre_slugs=["techno"])

    r1 = await client.get("/api/v1/genres")
    assert r1.status_code == 200
    assert spy.call_count == 1

    r2 = await client.get("/api/v1/genres")
    assert r2.status_code == 200
    assert spy.call_count == 1
    assert r1.json() == r2.json()


async def test_genres_cache_invalidates_after_ttl_expiry(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
    mocker: MockerFixture,
) -> None:
    spy = mocker.spy(genres_service, "fetch_genres_with_counts")

    await create_station(slug="ttl-1", genre_slugs=["techno"])
    r1 = await client.get("/api/v1/genres")
    assert r1.status_code == 200
    assert spy.call_count == 1

    redis: Redis[str] = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    await redis.delete(genres_service.CACHE_KEY)
    await redis.aclose()

    r2 = await client.get("/api/v1/genres")
    assert r2.status_code == 200
    assert spy.call_count == 2


async def test_genres_cache_manual_invalidation(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
    mocker: MockerFixture,
) -> None:
    spy = mocker.spy(genres_service, "fetch_genres_with_counts")

    await create_station(slug="inv-1", genre_slugs=["techno"])
    await client.get("/api/v1/genres")
    assert spy.call_count == 1

    redis: Redis[str] = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    await genres_service.invalidate_genres_cache(redis)
    await redis.aclose()

    await client.get("/api/v1/genres")
    assert spy.call_count == 2
