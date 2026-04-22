from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import httpx
from sqlalchemy import text

from icy_worker.icy_parser import parse_icy_metadata
from icy_worker.logging import get_logger
from icy_worker.np_state import publish_if_changed, state_key

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


log = get_logger("icy_worker.stream")

TITLE_PREVIEW_CHARS = 80

__all__ = ["read_icy_stream", "state_key"]


async def _persist_now_playing(
    maker: async_sessionmaker[AsyncSession],
    station_id: uuid.UUID,
    title: str | None,
    artist: str | None,
    raw: str,
) -> None:
    try:
        async with maker() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO now_playing (station_id, title, artist, raw_metadata)
                    VALUES (:sid, :title, :artist, :raw)
                    """,
                ),
                {
                    "sid": str(station_id),
                    "title": title,
                    "artist": artist,
                    "raw": raw,
                },
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning("now_playing_insert_failed", slug=str(station_id), error=str(exc))


def _truncate(value: str | None) -> str | None:
    if value is None:
        return None
    return value[:TITLE_PREVIEW_CHARS]


async def read_icy_stream(
    client: httpx.AsyncClient,
    url: str,
    *,
    redis: Redis[bytes],
    slug: str,
    station_id: uuid.UUID,
    maker: async_sessionmaker[AsyncSession],
    user_agent: str,
    persist_to_db: bool = True,
) -> None:
    """Conecta al stream ICY, emite metadata a Redis + tabla `now_playing`.

    Termina limpio ante cualquier excepción. No hace reconexión; el
    caller (OnDemandPool / AmbientLoop) decide si reintentar.
    """
    headers = {"Icy-MetaData": "1", "User-Agent": user_agent}

    try:
        async with client.stream("GET", url, headers=headers) as response:
            response.raise_for_status()
            metaint_raw = response.headers.get("icy-metaint")
            if not metaint_raw:
                log.warning("icy_no_metaint_header", slug=slug)
                return
            try:
                metaint = int(metaint_raw)
            except ValueError:
                log.warning("icy_invalid_metaint", slug=slug, value=metaint_raw)
                return

            byte_iter = response.aiter_bytes()
            buffer = bytearray()
            audio_remaining = metaint
            mode = "audio"
            length_byte: int | None = None
            meta_remaining = 0
            meta_buffer = bytearray()

            async for chunk in byte_iter:
                i = 0
                while i < len(chunk):
                    if mode == "audio":
                        take = min(audio_remaining, len(chunk) - i)
                        audio_remaining -= take
                        i += take
                        if audio_remaining == 0:
                            mode = "length"
                    elif mode == "length":
                        length_byte = chunk[i]
                        i += 1
                        meta_remaining = length_byte * 16
                        meta_buffer.clear()
                        if meta_remaining == 0:
                            # sin metadata esta vez
                            mode = "audio"
                            audio_remaining = metaint
                        else:
                            mode = "meta"
                    else:  # meta
                        take = min(meta_remaining, len(chunk) - i)
                        meta_buffer.extend(chunk[i : i + take])
                        meta_remaining -= take
                        i += take
                        if meta_remaining == 0:
                            parsed = parse_icy_metadata(bytes(meta_buffer))

                            if not parsed["raw"]:
                                mode = "audio"
                                audio_remaining = metaint
                                buffer.clear()
                                continue

                            changed = await publish_if_changed(
                                redis, slug, parsed["title"], parsed["artist"],
                            )
                            if changed:
                                if persist_to_db:
                                    await _persist_now_playing(
                                        maker,
                                        station_id,
                                        parsed["title"],
                                        parsed["artist"],
                                        parsed["raw"],
                                    )
                                log.info(
                                    "metadata_parsed",
                                    slug=slug,
                                    title=_truncate(parsed["title"]),
                                    artist=_truncate(parsed["artist"]),
                                )
                            else:
                                log.debug("metadata_no_change", slug=slug)

                            mode = "audio"
                            audio_remaining = metaint
                            buffer.clear()
    except httpx.HTTPError as exc:
        log.info("stream_error", slug=slug, error_type=type(exc).__name__, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        log.warning("stream_unexpected", slug=slug, error_type=type(exc).__name__, detail=str(exc))
