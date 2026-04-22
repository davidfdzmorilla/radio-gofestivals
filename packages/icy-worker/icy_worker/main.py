from __future__ import annotations

import asyncio
import contextlib
import signal

import httpx
import typer
from redis.asyncio import Redis

from icy_worker.ambient_loop import run_ambient_loop
from icy_worker.config import WorkerConfig, load_config
from icy_worker.db import make_engine, make_sessionmaker
from icy_worker.logging import get_logger
from icy_worker.ondemand_pool import OnDemandPool

log = get_logger("icy_worker.main")
app = typer.Typer(help="radio.gofestivals · ICY metadata worker")


async def _run(cfg: WorkerConfig) -> None:
    engine = make_engine(cfg.database_url)
    maker = make_sessionmaker(engine)
    redis: Redis[bytes] = Redis.from_url(cfg.redis_url, decode_responses=False)
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10.0, read=30.0, write=5.0, pool=5.0),
    )
    ambient_client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=cfg.ambient_probe_timeout, write=2.0, pool=2.0),
    )

    pool = OnDemandPool(
        redis=redis,
        maker=maker,
        client=client,
        user_agent=cfg.user_agent,
        concurrency=cfg.ondemand_concurrency,
        grace_seconds=cfg.ondemand_grace_seconds,
    )

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)

    ambient_task = asyncio.create_task(
        run_ambient_loop(
            redis=redis,
            maker=maker,
            client=ambient_client,
            user_agent=cfg.user_agent,
            interval=cfg.ambient_interval_seconds,
            top_n=cfg.ambient_top_n,
            concurrency=cfg.ambient_concurrency,
            probe_timeout=cfg.ambient_probe_timeout,
        ),
        name="ambient",
    )
    listen_task = asyncio.create_task(pool.listen_commands(), name="listen")
    stop_task = asyncio.create_task(stop_event.wait(), name="stop")

    log.info(
        "worker_ready",
        ondemand_concurrency=cfg.ondemand_concurrency,
        ambient_concurrency=cfg.ambient_concurrency,
        top_n=cfg.ambient_top_n,
    )

    done, pending = await asyncio.wait(
        {ambient_task, listen_task, stop_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    log.info("worker_shutdown_start")
    for t in pending:
        t.cancel()
    await pool.shutdown()
    for t in pending:
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await t
    await client.aclose()
    await ambient_client.aclose()
    await redis.aclose()  # type: ignore[attr-defined]
    await engine.dispose()
    log.info("worker_shutdown_done")


@app.command()
def serve() -> None:
    cfg = load_config()
    try:
        asyncio.run(_run(cfg))
    except KeyboardInterrupt:
        log.info("worker_interrupted")


@app.command()
def version() -> None:
    typer.echo("icy-worker 0.1.0")


if __name__ == "__main__":
    app()
