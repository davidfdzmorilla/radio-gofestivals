from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.core.db import get_engine

if TYPE_CHECKING:
    from httpx import AsyncClient


async def test_concurrent_genres_requests_release_pool_connections(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    """100 requests concurrentes a /api/v1/genres no deben dejar el pool drenado.

    Regresión del leak de sesiones en el WS de nowplaying y del wrapper
    `session_dep` envolviendo `get_session`. Si una request retiene su
    conexión más allá del response, el pool se agota silenciosamente y
    nuevas requests timeoutean.
    """
    await create_station(slug="leak-tek", genre_slugs=["techno"])

    async def hit() -> int:
        r = await client.get("/api/v1/genres")
        return r.status_code

    statuses = await asyncio.gather(*[hit() for _ in range(100)])
    assert all(s == 200 for s in statuses), f"non-200 in batch: {set(statuses)}"

    # Tras 100 requests, todas las conexiones deberían estar de vuelta en el
    # pool (checkedout == 0). Permitimos un margen pequeño por si hay alguna
    # operación interna en flight, pero la cota dura es < pool_size.
    pool = get_engine().pool
    checked_out = pool.checkedout()  # type: ignore[attr-defined]
    assert checked_out <= 1, (
        f"pool leak: {checked_out} connections still checked out after 100 reqs"
    )
