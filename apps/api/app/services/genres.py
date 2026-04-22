from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.repos.genres import fetch_genres_with_counts
from app.schemas.genre import GenreNode

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession


CACHE_KEY = "genres:tree:v1"


def _build_tree(rows: list[tuple[int, str, str, str, int | None, int, int]]) -> list[GenreNode]:
    by_id: dict[int, GenreNode] = {}
    order: list[int] = []
    for row in rows:
        gid, slug, name, color_hex, parent_id, _sort_order, station_count = row
        by_id[gid] = GenreNode(
            id=gid,
            slug=slug,
            name=name,
            color_hex=color_hex,
            parent_id=parent_id,
            station_count=station_count,
        )
        order.append(gid)
    roots: list[GenreNode] = []
    for gid in order:
        node = by_id[gid]
        if node.parent_id is not None and node.parent_id in by_id:
            by_id[node.parent_id].children.append(node)
        else:
            roots.append(node)
    return roots


async def get_genres_tree(
    session: AsyncSession,
    redis: Redis[str],
    ttl: int,
) -> list[GenreNode]:
    cached = await redis.get(CACHE_KEY)
    if cached is not None:
        return [GenreNode.model_validate(item) for item in json.loads(cached)]

    rows = await fetch_genres_with_counts(session)
    tree = _build_tree([tuple(r) for r in rows])  # type: ignore[misc]
    payload = json.dumps([node.model_dump() for node in tree])
    await redis.set(CACHE_KEY, payload, ex=ttl)
    return tree


async def invalidate_genres_cache(redis: Redis[str]) -> None:
    await redis.delete(CACHE_KEY)
