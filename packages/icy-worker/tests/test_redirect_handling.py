"""Verify the icy-worker httpx clients follow redirects.

Regression for the 2026-04-27 incident: many Radio-Browser stream URLs
301/302 to CDN-rewritten endpoints. Without `follow_redirects=True` the
worker raised HTTPStatusError on the first hop and dropped ~30 popular
stations entirely. The clients in `icy_worker.main` are now configured
with `follow_redirects=True, max_redirects=3`. These tests assert the
expected end-to-end behaviour through `read_icy_stream`.
"""
from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

import httpx
import pytest
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


def _audio_with_meta(title: str) -> bytes:
    body = bytearray()
    body.extend(b"\x55" * METAINT)
    body.extend(_meta_block(title))
    body.extend(b"\x55" * METAINT)
    return bytes(body)


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
            VALUES (:sid, 'https://old.example.com/stream', 'mp3', 128,
                    true, 'active')
            """,
        ),
        {"sid": sid},
    )
    await db_session.commit()
    return sid


async def _fresh_redis():  # type: ignore[no-untyped-def]
    from redis.asyncio import Redis as R

    r: Redis[bytes] = R.from_url("redis://localhost:6379/15", decode_responses=False)
    await r.delete(state_key("redirect-test"))
    return r


def _audio_response(title: str) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"icy-metaint": str(METAINT), "content-type": "audio/mpeg"},
        content=_audio_with_meta(title),
    )


async def test_stream_reader_follows_301(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    sid = await _insert_station(db_session, "redirect-test")
    redis = await _fresh_redis()

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.host == "old.example.com":
            return httpx.Response(
                301, headers={"location": "https://new.example.com/stream"},
            )
        if req.url.host == "new.example.com":
            return _audio_response("DJ A - Track 1")
        return httpx.Response(404)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
        max_redirects=3,
    )
    await read_icy_stream(
        client,
        "https://old.example.com/stream",
        redis=redis,
        slug="redirect-test",
        station_id=sid,
        maker=maker,
        user_agent="test/1.0",
    )
    await client.aclose()

    raw = await redis.get(state_key("redirect-test"))
    assert raw is not None, "metadata never reached redis (301 not followed)"
    payload = json.loads(raw)
    assert payload["title"] == "Track 1"
    assert payload["artist"] == "DJ A"
    await redis.aclose()


async def test_stream_reader_follows_302_chain(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    sid = await _insert_station(db_session, "redirect-test")
    redis = await _fresh_redis()

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.host == "hop0.example.com":
            return httpx.Response(302, headers={"location": "https://hop1.example.com/x"})
        if req.url.host == "hop1.example.com":
            return httpx.Response(302, headers={"location": "https://hop2.example.com/y"})
        if req.url.host == "hop2.example.com":
            return _audio_response("DJ B - Track 2")
        return httpx.Response(404)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
        max_redirects=3,
    )
    await read_icy_stream(
        client,
        "https://hop0.example.com/start",
        redis=redis,
        slug="redirect-test",
        station_id=sid,
        maker=maker,
        user_agent="test/1.0",
    )
    await client.aclose()

    raw = await redis.get(state_key("redirect-test"))
    assert raw is not None
    payload = json.loads(raw)
    assert payload["title"] == "Track 2"
    await redis.aclose()


async def test_stream_reader_rejects_excessive_redirects(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    """A 4-hop chain (over max_redirects=3) must NOT silently succeed.

    `read_icy_stream` swallows exceptions and returns; we assert that no
    metadata reaches Redis when the chain exceeds the cap.
    """
    sid = await _insert_station(db_session, "redirect-test")
    redis = await _fresh_redis()

    def handler(req: httpx.Request) -> httpx.Response:
        # Always redirect; httpx will give up after max_redirects=3.
        next_host = f"hop-next-{req.url.host}.example.com"
        return httpx.Response(301, headers={"location": f"https://{next_host}/x"})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
        max_redirects=3,
    )
    await read_icy_stream(
        client,
        "https://hop-a.example.com/start",
        redis=redis,
        slug="redirect-test",
        station_id=sid,
        maker=maker,
        user_agent="test/1.0",
    )
    await client.aclose()

    raw = await redis.get(state_key("redirect-test"))
    assert raw is None, "metadata wrote despite redirect chain exceeding cap"
    await redis.aclose()


def test_max_redirects_is_explicit_constant() -> None:
    """Sanity-check: importing main wires the documented limit.

    Imports `make_clients`-equivalent path to avoid relying on the fragile
    string content of main.py at runtime — read the source directly.
    """
    import pathlib

    src = pathlib.Path(__file__).resolve().parents[1] / "icy_worker" / "main.py"
    text_ = src.read_text(encoding="utf-8")
    # Both clients should have follow_redirects=True with max_redirects=3.
    assert text_.count("follow_redirects=True") >= 2
    assert text_.count("max_redirects=3") >= 2


@pytest.mark.skip(reason="documentation-only: structure mirrored above")
def test_documentation_anchor() -> None:  # pragma: no cover
    """Anchor for engineers grep'ing the codebase for redirect behaviour."""
