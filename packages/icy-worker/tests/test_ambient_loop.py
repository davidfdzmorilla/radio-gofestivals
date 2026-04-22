from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import httpx
from sqlalchemy import text

from icy_worker.ambient_loop import run_ambient_loop, top_stations

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def _seed(db_session: AsyncSession, *, curated: bool, status: str, score: int, slug: str) -> None:
    await db_session.execute(
        text(
            """
            INSERT INTO stations (slug, name, stream_url, curated, status, quality_score)
            VALUES (:slug, :slug, 'https://unreachable.test/s', :c, :st, :sc)
            """,
        ),
        {"slug": slug, "c": curated, "st": status, "sc": score},
    )
    await db_session.commit()


async def test_queries_top_curated(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(db_session, curated=True, status="active", score=90, slug="high")
    await _seed(db_session, curated=True, status="active", score=50, slug="mid")
    await _seed(db_session, curated=False, status="active", score=99, slug="uncurated")
    await _seed(db_session, curated=True, status="pending", score=99, slug="pending")

    rows = await top_stations(maker, top_n=10)
    slugs = [r[1] for r in rows]
    assert slugs == ["high", "mid"]


async def test_ambient_iteration_runs_probes(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(db_session, curated=True, status="active", score=90, slug="amb-1")

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={}, content=b"\x00" * 8)

    from redis.asyncio import Redis

    redis: Redis = Redis.from_url("redis://localhost:6379/15", decode_responses=False)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    await run_ambient_loop(
        redis=redis,
        maker=maker,
        client=client,
        user_agent="test/1.0",
        interval=0,
        top_n=10,
        concurrency=2,
        probe_timeout=1.0,
        iterations=1,
    )
    await client.aclose()
    await redis.aclose()


async def test_ambient_uses_own_semaphore(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    """Si se inyecta un semaphore externo, el loop lo usa tal cual
    (separado del OnDemandPool)."""
    import asyncio as _asyncio

    await _seed(db_session, curated=True, status="active", score=90, slug="own-sem")

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={}, content=b"\x00" * 4)

    from redis.asyncio import Redis

    redis: Redis = Redis.from_url("redis://localhost:6379/15", decode_responses=False)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    injected_sem = _asyncio.Semaphore(3)

    await run_ambient_loop(
        redis=redis,
        maker=maker,
        client=client,
        user_agent="test/1.0",
        interval=0,
        top_n=10,
        concurrency=99,  # ignorado porque se pasa `sem`
        probe_timeout=1.0,
        iterations=1,
        sem=injected_sem,
    )

    # El semaphore sigue libre tras el loop
    assert injected_sem._value == 3  # noqa: SLF001

    await client.aclose()
    await redis.aclose()


async def test_ambient_does_not_write_now_playing(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    sid = uuid.UUID(
        str(
            (
                await db_session.execute(
                    text(
                        """
                        INSERT INTO stations (slug, name, stream_url, curated, status, quality_score)
                        VALUES ('amb2', 'amb2', 'https://x/y', true, 'active', 50)
                        RETURNING id
                        """,
                    ),
                )
            ).scalar_one(),
        ),
    )
    await db_session.commit()

    # Simula respuesta con metadata real
    def handler(_req: httpx.Request) -> httpx.Response:
        body = b"\x55" * 16 + bytes([1]) + b"StreamTitle='X - Y';" + b"\x00" * (
            16 - len(b"StreamTitle='X - Y';") % 16
        )
        return httpx.Response(
            200,
            headers={"icy-metaint": "16"},
            content=body,
        )

    from redis.asyncio import Redis

    redis: Redis = Redis.from_url("redis://localhost:6379/15", decode_responses=False)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    await run_ambient_loop(
        redis=redis,
        maker=maker,
        client=client,
        user_agent="test/1.0",
        interval=0,
        top_n=10,
        concurrency=2,
        probe_timeout=1.0,
        iterations=1,
    )

    rows = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM now_playing WHERE station_id = :id"),
            {"id": str(sid)},
        )
    ).scalar_one()
    assert rows == 0
    await client.aclose()
    await redis.aclose()
