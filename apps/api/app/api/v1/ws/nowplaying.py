from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy import text

from app.api.deps import RedisDep, SessionDep
from app.core.logging import get_logger
from app.services.rate_limit import check_rate_limit

router = APIRouter()
log = get_logger("app.ws.nowplaying")

WS_CONN_LIMIT_PER_IP = 5
WS_CONN_WINDOW_SECONDS = 60
STATE_KEY_PREFIX = "np:state:"
POLL_INTERVAL_SECONDS = 2.0
HEARTBEAT_EVERY_SECONDS = 30.0


async def _station_is_active(session: Any, slug: str) -> bool:
    row = (
        await session.execute(
            text("SELECT 1 FROM stations WHERE slug = :slug AND status = 'active'"),
            {"slug": slug},
        )
    ).first()
    return row is not None


@router.websocket("/ws/nowplaying/{slug}")
async def nowplaying_ws(
    ws: WebSocket,
    slug: str,
    session: SessionDep,
    redis: RedisDep,
) -> None:
    client_ip = ws.client.host if ws.client else "unknown"
    allowed, _count = await check_rate_limit(
        redis,
        f"ws_nowplaying:{client_ip}",
        limit=WS_CONN_LIMIT_PER_IP,
        window_seconds=WS_CONN_WINDOW_SECONDS,
    )
    if not allowed:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="rate_limited")
        return

    if not await _station_is_active(session, slug):
        await ws.accept()
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="station_not_available")
        return

    await ws.accept()
    await redis.publish("icy:subscribe", slug)
    log.info("ws_connected", slug=slug, ip=client_ip)

    key = f"{STATE_KEY_PREFIX}{slug}"

    async def _poll_and_send() -> None:
        last_sent: str | None = None
        heartbeat_accum = 0.0

        initial = await redis.get(key)
        if initial:
            payload = initial.decode("utf-8") if isinstance(initial, bytes) else initial
            await ws.send_text(payload)
            last_sent = payload

        while True:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            heartbeat_accum += POLL_INTERVAL_SECONDS
            raw = await redis.get(key)
            if raw is not None:
                payload = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                if payload != last_sent:
                    await ws.send_text(payload)
                    last_sent = payload
                    heartbeat_accum = 0.0
            if heartbeat_accum >= HEARTBEAT_EVERY_SECONDS:
                await ws.send_text('{"heartbeat":true}')
                heartbeat_accum = 0.0

    async def _await_disconnect() -> None:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                return

    poll_task = asyncio.create_task(_poll_and_send(), name=f"ws-poll:{slug}")
    disc_task = asyncio.create_task(_await_disconnect(), name=f"ws-recv:{slug}")

    try:
        done, pending = await asyncio.wait(
            {poll_task, disc_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
        for t in done:
            exc = t.exception()
            if exc is not None and not isinstance(exc, WebSocketDisconnect):
                log.warning("ws_error", slug=slug, error=str(exc))
        log.info("ws_disconnected", slug=slug, ip=client_ip)
    finally:
        for t in (poll_task, disc_task):
            if not t.done():
                t.cancel()
        # asyncio.shield: cuando el handler mismo es cancelado (TestClient
        # cleanup, server shutdown), queremos que el publish SÍ llegue al
        # broker para que el icy-worker libere el stream on-demand. Sin
        # shield, el `await` dentro del finally de una task cancelled se
        # re-lanza como CancelledError antes de ejecutar la operación.
        publish_task = asyncio.ensure_future(redis.publish("icy:release", slug))
        try:
            await asyncio.shield(publish_task)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("ws_release_publish_failed", slug=slug, error=str(exc))
