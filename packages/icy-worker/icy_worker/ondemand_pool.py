from __future__ import annotations

import asyncio
import contextlib
import uuid
from typing import TYPE_CHECKING

import httpx
from sqlalchemy import text

from icy_worker.logging import get_logger
from icy_worker.stream_reader import read_icy_stream

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


log = get_logger("icy_worker.ondemand")

SUBSCRIBE_CHANNEL = "icy:subscribe"
RELEASE_CHANNEL = "icy:release"


async def _resolve_station(
    maker: async_sessionmaker[AsyncSession], slug: str,
) -> tuple[uuid.UUID, str] | None:
    async with maker() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT s.id, ss.stream_url
                    FROM stations s
                    JOIN station_streams ss
                      ON ss.station_id = s.id AND ss.is_primary = true
                    WHERE s.slug = :slug
                      AND s.status = 'active'
                      AND ss.status = 'active'
                    """,
                ),
                {"slug": slug},
            )
        ).first()
    if row is None:
        return None
    return uuid.UUID(str(row[0])), str(row[1])


class OnDemandPool:
    """Gestiona workers ICY on-demand con refcount y grace period.

    Semaphore DEDICADO (no compartido con AmbientLoop) para que una
    avalancha de conexiones WS no deje sin slots el polling ambient.

    Concurrencia interna: toda mutación de estado pasa por `_lock`,
    un `asyncio.Lock` local al event loop. Como el worker corre en un
    único event loop y todas las operaciones (subscribe/release/
    _grace_close) son corutinas que adquieren ese lock, no hay race
    condition real entre ellas — el lock codifica explícitamente la
    invariante "mutación atómica del trío (refcount, tasks, grace_tasks)".
    """

    def __init__(
        self,
        *,
        redis: Redis[bytes],
        maker: async_sessionmaker[AsyncSession],
        client: httpx.AsyncClient,
        user_agent: str,
        concurrency: int = 40,
        grace_seconds: int = 60,
    ) -> None:
        self._redis = redis
        self._maker = maker
        self._client = client
        self._user_agent = user_agent
        self._sem = asyncio.Semaphore(concurrency)
        self._grace = grace_seconds
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._refcount: dict[str, int] = {}
        self._grace_tasks: dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, slug: str) -> None:
        async with self._lock:
            self._refcount[slug] = self._refcount.get(slug, 0) + 1
            grace = self._grace_tasks.pop(slug, None)
            if grace is not None and not grace.done():
                grace.cancel()
            if slug in self._tasks and not self._tasks[slug].done():
                log.info(
                    "worker_subscribe",
                    slug=slug,
                    refcount=self._refcount[slug],
                    reused=True,
                )
                return
            task = asyncio.create_task(self._run_slug(slug), name=f"icy:{slug}")
            self._tasks[slug] = task
            log.info("worker_subscribe", slug=slug, refcount=self._refcount[slug], reused=False)

    async def release(self, slug: str) -> None:
        async with self._lock:
            if slug not in self._refcount:
                return
            self._refcount[slug] = max(0, self._refcount[slug] - 1)
            log.info("worker_release", slug=slug, refcount=self._refcount[slug])
            if self._refcount[slug] > 0:
                return
            existing_grace = self._grace_tasks.get(slug)
            if existing_grace is not None and not existing_grace.done():
                return
            self._grace_tasks[slug] = asyncio.create_task(
                self._grace_close(slug), name=f"grace:{slug}",
            )

    async def _grace_close(self, slug: str) -> None:
        try:
            await asyncio.sleep(self._grace)
        except asyncio.CancelledError:
            return
        async with self._lock:
            if self._refcount.get(slug, 0) > 0:
                return
            task = self._tasks.pop(slug, None)
            self._refcount.pop(slug, None)
            self._grace_tasks.pop(slug, None)
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        log.info("worker_task_ended", slug=slug, reason="released")

    async def _run_slug(self, slug: str) -> None:
        async with self._sem:
            log.info("worker_task_started", slug=slug)
            resolved = await _resolve_station(self._maker, slug)
            if resolved is None:
                log.warning("worker_station_missing", slug=slug)
                return
            station_id, stream_url = resolved
            try:
                await read_icy_stream(
                    self._client,
                    stream_url,
                    redis=self._redis,
                    slug=slug,
                    station_id=station_id,
                    maker=self._maker,
                    user_agent=self._user_agent,
                    persist_to_db=True,
                )
            except asyncio.CancelledError:
                log.info("worker_task_ended", slug=slug, reason="cancelled")
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning("worker_task_error", slug=slug, error=str(exc))
            finally:
                log.info("worker_task_ended", slug=slug, reason="finished")

    async def listen_commands(self) -> None:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(SUBSCRIBE_CHANNEL, RELEASE_CHANNEL)
        try:
            async for msg in pubsub.listen():
                if msg.get("type") != "message":
                    continue
                channel = msg.get("channel")
                data = msg.get("data")
                if isinstance(data, bytes):
                    slug = data.decode("utf-8")
                else:
                    slug = str(data)
                if isinstance(channel, bytes):
                    channel = channel.decode("utf-8")
                if channel == SUBSCRIBE_CHANNEL:
                    await self.subscribe(slug)
                elif channel == RELEASE_CHANNEL:
                    await self.release(slug)
        finally:
            await pubsub.aclose()  # type: ignore[attr-defined]

    async def shutdown(self) -> None:
        async with self._lock:
            tasks = list(self._tasks.values()) + list(self._grace_tasks.values())
            self._tasks.clear()
            self._grace_tasks.clear()
            self._refcount.clear()
        for t in tasks:
            t.cancel()
        for t in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
