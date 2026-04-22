from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

import httpx
from sqlalchemy import text

from icy_worker.stream_reader import read_icy_stream, state_key

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


METAINT = 16


def _meta_block(title: str) -> bytes:
    payload = f"StreamTitle='{title}';".encode("latin-1")
    blocks = (len(payload) + 15) // 16
    padded = payload + b"\x00" * (blocks * 16 - len(payload))
    return bytes([blocks]) + padded


def _build_response(
    *,
    metas: list[str],
    metaint: int = METAINT,
    audio_byte: int = 0x55,
) -> httpx.Response:
    body = bytearray()
    for title in metas:
        body.extend(bytes([audio_byte]) * metaint)
        body.extend(_meta_block(title))
    body.extend(bytes([audio_byte]) * metaint)
    return httpx.Response(
        200,
        headers={"icy-metaint": str(metaint), "content-type": "audio/mpeg"},
        content=bytes(body),
    )


def _build_no_metaint() -> httpx.Response:
    return httpx.Response(200, headers={}, content=b"\x55" * 32)


def _transport_for(response: httpx.Response) -> httpx.MockTransport:
    def handler(_req: httpx.Request) -> httpx.Response:
        return response

    return httpx.MockTransport(handler)


async def _insert_station(db_session: AsyncSession, slug: str) -> uuid.UUID:
    result = await db_session.execute(
        text(
            """
            INSERT INTO stations (slug, name, stream_url, status)
            VALUES (:slug, :slug, 'https://example.com/s', 'active')
            RETURNING id
            """,
        ),
        {"slug": slug},
    )
    await db_session.commit()
    return uuid.UUID(str(result.scalar_one()))


async def _fresh_redis() -> Redis:
    from redis.asyncio import Redis as R

    r: Redis = R.from_url("redis://localhost:6379/15", decode_responses=False)
    await r.delete(state_key("stream-test"))
    return r


async def test_reads_single_metadata_chunk(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    sid = await _insert_station(db_session, "stream-test")
    redis = await _fresh_redis()

    client = httpx.AsyncClient(
        transport=_transport_for(_build_response(metas=["Artist X - Track Y"])),
    )
    await read_icy_stream(
        client,
        "https://example.com/s",
        redis=redis,
        slug="stream-test",
        station_id=sid,
        maker=maker,
        user_agent="test/1.0",
    )
    await client.aclose()

    raw_state = await redis.get(state_key("stream-test"))
    assert raw_state is not None
    payload = json.loads(raw_state)
    assert payload["title"] == "Track Y"
    assert payload["artist"] == "Artist X"
    await redis.aclose()


async def test_dedupe_same_metadata(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    sid = await _insert_station(db_session, "stream-test")
    redis = await _fresh_redis()

    client = httpx.AsyncClient(
        transport=_transport_for(
            _build_response(metas=["A - B", "A - B", "A - B"]),
        ),
    )
    await read_icy_stream(
        client,
        "https://example.com/s",
        redis=redis,
        slug="stream-test",
        station_id=sid,
        maker=maker,
        user_agent="test/1.0",
    )
    await client.aclose()

    rows = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM now_playing WHERE station_id = :id"),
            {"id": str(sid)},
        )
    ).scalar_one()
    assert rows == 1
    await redis.aclose()


async def test_writes_to_now_playing_table(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    sid = await _insert_station(db_session, "stream-test")
    redis = await _fresh_redis()

    client = httpx.AsyncClient(
        transport=_transport_for(_build_response(metas=["DJ - Cut"])),
    )
    await read_icy_stream(
        client,
        "https://example.com/s",
        redis=redis,
        slug="stream-test",
        station_id=sid,
        maker=maker,
        user_agent="test/1.0",
        persist_to_db=True,
    )
    await client.aclose()

    row = (
        await db_session.execute(
            text(
                "SELECT title, artist, raw_metadata FROM now_playing "
                "WHERE station_id = :id",
            ),
            {"id": str(sid)},
        )
    ).first()
    assert row is not None
    assert row[0] == "Cut"
    assert row[1] == "DJ"
    assert row[2] == "DJ - Cut"
    await redis.aclose()


async def test_no_metaint_header_exits(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    sid = await _insert_station(db_session, "stream-test")
    redis = await _fresh_redis()

    client = httpx.AsyncClient(transport=_transport_for(_build_no_metaint()))
    await read_icy_stream(
        client,
        "https://example.com/s",
        redis=redis,
        slug="stream-test",
        station_id=sid,
        maker=maker,
        user_agent="test/1.0",
    )
    await client.aclose()

    state = await redis.get(state_key("stream-test"))
    assert state is None
    await redis.aclose()


async def test_disconnect_handled(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    sid = await _insert_station(db_session, "stream-test")
    redis = await _fresh_redis()

    def handler(_req: httpx.Request) -> httpx.Response:
        raise httpx.ReadError("connection dropped")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    # Should not raise
    await read_icy_stream(
        client,
        "https://example.com/s",
        redis=redis,
        slug="stream-test",
        station_id=sid,
        maker=maker,
        user_agent="test/1.0",
    )
    await client.aclose()
    await redis.aclose()


async def test_latin1_decoding_works(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    sid = await _insert_station(db_session, "stream-test")
    redis = await _fresh_redis()

    client = httpx.AsyncClient(
        transport=_transport_for(_build_response(metas=["Café - Ñoño"])),
    )
    await read_icy_stream(
        client,
        "https://example.com/s",
        redis=redis,
        slug="stream-test",
        station_id=sid,
        maker=maker,
        user_agent="test/1.0",
    )
    await client.aclose()

    raw_state = await redis.get(state_key("stream-test"))
    assert raw_state is not None
    payload = json.loads(raw_state)
    assert payload["artist"] == "Café"
    assert payload["title"] == "Ñoño"
    await redis.aclose()
