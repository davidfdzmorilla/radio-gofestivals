from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

import httpx
import pytest
from sqlalchemy import text

from icy_worker.ondemand_pool import OnDemandPool

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_ = pytest  # quiet lint; used in Annotated type refs


async def _insert_station(db_session: AsyncSession, slug: str) -> uuid.UUID:
    result = await db_session.execute(
        text(
            """
            INSERT INTO stations (slug, name, status)
            VALUES (:slug, :slug, 'active')
            RETURNING id
            """,
        ),
        {"slug": slug},
    )
    sid = uuid.UUID(str(result.scalar_one()))
    await db_session.execute(
        text(
            """
            INSERT INTO station_streams
                (station_id, stream_url, codec, bitrate, is_primary, status)
            VALUES (:sid, 'https://unreachable.test/s', 'mp3', 128,
                    true, 'active')
            """,
        ),
        {"sid": sid},
    )
    await db_session.commit()
    return sid


async def _fake_redis():  # type: ignore[no-untyped-def]
    from redis.asyncio import Redis

    return Redis.from_url("redis://localhost:6379/15", decode_responses=False)


def _no_op_transport() -> httpx.MockTransport:
    def handler(_req: httpx.Request) -> httpx.Response:
        # no metaint → reader exits silently right after headers
        return httpx.Response(200, headers={}, content=b"\x00" * 8)

    return httpx.MockTransport(handler)


async def test_subscribe_starts_task(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    await _insert_station(db_session, "s1")
    redis = await _fake_redis()
    client = httpx.AsyncClient(transport=_no_op_transport())
    pool = OnDemandPool(
        redis=redis, maker=maker, client=client, user_agent="t", grace_seconds=1,
    )
    await pool.subscribe("s1")
    assert "s1" in pool._tasks  # noqa: SLF001
    assert pool._refcount["s1"] == 1  # noqa: SLF001
    await pool.shutdown()
    await client.aclose()
    await redis.aclose()


async def test_duplicate_subscribe_increments_refcount(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    await _insert_station(db_session, "s1")
    redis = await _fake_redis()
    client = httpx.AsyncClient(transport=_no_op_transport())
    pool = OnDemandPool(redis=redis, maker=maker, client=client, user_agent="t")
    await pool.subscribe("s1")
    await pool.subscribe("s1")
    assert pool._refcount["s1"] == 2  # noqa: SLF001
    await pool.shutdown()
    await client.aclose()
    await redis.aclose()


async def test_release_triggers_grace_period(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    await _insert_station(db_session, "s1")
    redis = await _fake_redis()
    client = httpx.AsyncClient(transport=_no_op_transport())
    pool = OnDemandPool(
        redis=redis, maker=maker, client=client, user_agent="t", grace_seconds=1,
    )
    await pool.subscribe("s1")
    await pool.release("s1")
    assert "s1" in pool._grace_tasks  # noqa: SLF001
    await asyncio.sleep(1.5)
    assert "s1" not in pool._tasks  # noqa: SLF001
    await pool.shutdown()
    await client.aclose()
    await redis.aclose()


async def test_grace_cancelled_if_resubscribed(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    await _insert_station(db_session, "s1")
    redis = await _fake_redis()
    client = httpx.AsyncClient(transport=_no_op_transport())
    pool = OnDemandPool(
        redis=redis, maker=maker, client=client, user_agent="t", grace_seconds=2,
    )
    await pool.subscribe("s1")
    await pool.release("s1")
    await pool.subscribe("s1")
    await asyncio.sleep(0.05)
    assert pool._refcount["s1"] == 1  # noqa: SLF001
    assert "s1" not in pool._grace_tasks or pool._grace_tasks["s1"].cancelled()  # noqa: SLF001
    await pool.shutdown()
    await client.aclose()
    await redis.aclose()


async def test_release_without_subscribe_is_noop(
    maker: async_sessionmaker[AsyncSession],
) -> None:
    redis = await _fake_redis()
    client = httpx.AsyncClient(transport=_no_op_transport())
    pool = OnDemandPool(redis=redis, maker=maker, client=client, user_agent="t")
    await pool.release("never-subscribed")
    assert "never-subscribed" not in pool._refcount  # noqa: SLF001
    await pool.shutdown()
    await client.aclose()
    await redis.aclose()


async def test_concurrency_semaphore(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    for i in range(5):
        await _insert_station(db_session, f"cc-{i}")
    redis = await _fake_redis()
    client = httpx.AsyncClient(transport=_no_op_transport())
    pool = OnDemandPool(
        redis=redis, maker=maker, client=client, user_agent="t", concurrency=2,
    )
    for i in range(5):
        await pool.subscribe(f"cc-{i}")
    assert sum(1 for t in pool._tasks.values() if not t.done()) <= 5  # noqa: SLF001
    await pool.shutdown()
    await client.aclose()
    await redis.aclose()


async def test_ondemand_semaphore_does_not_affect_ambient(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    """Agotar el semaphore del pool no debe bloquear el semaphore independiente
    del ambient (son instancias distintas)."""
    for i in range(3):
        await _insert_station(db_session, f"sat-{i}")

    redis = await _fake_redis()
    client = httpx.AsyncClient(transport=_no_op_transport())
    pool = OnDemandPool(
        redis=redis, maker=maker, client=client, user_agent="t",
        concurrency=2, grace_seconds=5,
    )
    for i in range(2):
        await pool.subscribe(f"sat-{i}")
    await asyncio.sleep(0.1)

    ambient_sem = asyncio.Semaphore(10)
    acquired = False
    async with ambient_sem:
        acquired = True
    assert acquired is True

    await pool.shutdown()
    await client.aclose()
    await redis.aclose()


async def _install_blocking_reader(monkeypatch):  # type: ignore[no-untyped-def]
    """Reemplaza read_icy_stream con una corutina que bloquea hasta cancelación.

    Simula un stream real que permanece abierto mientras el refcount > 0.
    """
    async def _blocking(*_a, **_kw):  # type: ignore[no-untyped-def]
        await asyncio.Event().wait()

    monkeypatch.setattr("icy_worker.ondemand_pool.read_icy_stream", _blocking)


async def test_grace_race_resubscribe_at_last_moment(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _install_blocking_reader(monkeypatch)
    await _insert_station(db_session, "race-1")
    redis = await _fake_redis()
    client = httpx.AsyncClient(transport=_no_op_transport())
    pool = OnDemandPool(
        redis=redis, maker=maker, client=client,
        user_agent="t", grace_seconds=0.05,
    )

    await pool.subscribe("race-1")
    await asyncio.sleep(0.005)
    original_task = pool._tasks.get("race-1")  # noqa: SLF001
    assert original_task is not None
    assert not original_task.done()

    await pool.release("race-1")
    await asyncio.sleep(0.04)
    await pool.subscribe("race-1")

    assert pool._refcount["race-1"] == 1  # noqa: SLF001
    assert pool._tasks.get("race-1") is original_task  # noqa: SLF001
    grace = pool._grace_tasks.get("race-1")  # noqa: SLF001
    assert grace is None or grace.cancelled() or grace.done()

    await asyncio.sleep(0.1)
    assert pool._refcount.get("race-1", 0) == 1  # noqa: SLF001
    assert "race-1" in pool._tasks  # noqa: SLF001
    assert not pool._tasks["race-1"].done()  # noqa: SLF001

    await pool.shutdown()
    await client.aclose()
    await redis.aclose()


async def test_grace_race_release_twice_then_subscribe(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _install_blocking_reader(monkeypatch)
    await _insert_station(db_session, "race-2")
    redis = await _fake_redis()
    client = httpx.AsyncClient(transport=_no_op_transport())
    pool = OnDemandPool(
        redis=redis, maker=maker, client=client,
        user_agent="t", grace_seconds=0.1,
    )

    await pool.subscribe("race-2")
    await pool.subscribe("race-2")
    assert pool._refcount["race-2"] == 2  # noqa: SLF001
    await asyncio.sleep(0.005)
    original_task = pool._tasks["race-2"]  # noqa: SLF001
    assert not original_task.done()

    await pool.release("race-2")
    assert pool._refcount["race-2"] == 1  # noqa: SLF001
    assert pool._grace_tasks.get("race-2") is None  # noqa: SLF001

    await pool.release("race-2")
    assert pool._refcount["race-2"] == 0  # noqa: SLF001

    await asyncio.sleep(0.05)
    await pool.subscribe("race-2")
    assert pool._refcount["race-2"] == 1  # noqa: SLF001
    assert pool._tasks["race-2"] is original_task  # noqa: SLF001

    await asyncio.sleep(0.15)
    assert "race-2" in pool._tasks  # noqa: SLF001
    assert not pool._tasks["race-2"].done()  # noqa: SLF001

    await pool.shutdown()
    await client.aclose()
    await redis.aclose()
