from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

import httpx
from sqlalchemy import text

from icy_worker.logging import get_logger
from icy_worker.stream_reader import read_icy_stream

if TYPE_CHECKING:
    from collections.abc import Sequence

    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


log = get_logger("icy_worker.ambient")


async def _top_stations(
    maker: async_sessionmaker[AsyncSession], top_n: int,
) -> list[tuple[uuid.UUID, str, str]]:
    async with maker() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT id, slug, stream_url FROM stations
                    WHERE curated = true AND status = 'active'
                    ORDER BY quality_score DESC, name ASC
                    LIMIT :n
                    """,
                ),
                {"n": top_n},
            )
        ).all()
    return [(uuid.UUID(str(r[0])), str(r[1]), str(r[2])) for r in rows]


async def _probe_one(
    sem: asyncio.Semaphore,
    client: httpx.AsyncClient,
    *,
    redis: Redis[bytes],
    station: tuple[uuid.UUID, str, str],
    maker: async_sessionmaker[AsyncSession],
    probe_timeout: float,
    user_agent: str,
) -> None:
    station_id, slug, url = station
    async with sem:
        try:
            await asyncio.wait_for(
                read_icy_stream(
                    client,
                    url,
                    redis=redis,
                    slug=slug,
                    station_id=station_id,
                    maker=maker,
                    user_agent=user_agent,
                    persist_to_db=False,
                ),
                timeout=probe_timeout,
            )
        except TimeoutError:
            log.debug("ambient_probe_timeout", slug=slug)


async def run_ambient_loop(
    *,
    redis: Redis[bytes],
    maker: async_sessionmaker[AsyncSession],
    client: httpx.AsyncClient,
    user_agent: str,
    interval: int = 60,
    top_n: int = 50,
    concurrency: int = 10,
    probe_timeout: float = 10.0,
    iterations: int | None = None,
    sem: asyncio.Semaphore | None = None,
) -> None:
    """Polling periódico de las top-N curated stations.

    Usa un semaphore PROPIO (inyectable vía `sem` o autogenerado a partir
    de `concurrency`) separado del OnDemandPool para que el ambient siga
    operativo aunque on-demand sature su presupuesto de conexiones.
    """
    if sem is None:
        sem = asyncio.Semaphore(concurrency)
    count = 0
    while True:
        stations = await _top_stations(maker, top_n)
        log.info("ambient_tick_start", count=len(stations))
        await asyncio.gather(
            *(
                _probe_one(
                    sem,
                    client,
                    redis=redis,
                    station=s,
                    maker=maker,
                    probe_timeout=probe_timeout,
                    user_agent=user_agent,
                )
                for s in stations
            ),
        )
        log.info("ambient_tick_done")
        count += 1
        if iterations is not None and count >= iterations:
            return
        await asyncio.sleep(interval)


async def top_stations(
    maker: async_sessionmaker[AsyncSession], top_n: int,
) -> Sequence[tuple[uuid.UUID, str, str]]:
    return await _top_stations(maker, top_n)
