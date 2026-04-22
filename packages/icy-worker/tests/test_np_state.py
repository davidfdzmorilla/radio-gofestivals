from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from redis.asyncio import Redis

from icy_worker.np_state import publish_if_changed, state_key


@pytest_asyncio.fixture
async def redis_client():  # type: ignore[no-untyped-def]
    r: Redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=False)
    await r.delete(state_key("np-test"))
    yield r
    await r.delete(state_key("np-test"))
    await r.aclose()  # type: ignore[attr-defined]


async def test_first_call_sets_value(redis_client: Redis) -> None:
    changed = await publish_if_changed(redis_client, "np-test", "T1", "A1")
    assert changed is True
    raw = await redis_client.get(state_key("np-test"))
    assert raw is not None


async def test_no_rewrite_if_metadata_same(redis_client: Redis) -> None:
    now1 = datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC)
    await publish_if_changed(redis_client, "np-test", "T", "A", now=now1)

    now2 = now1 + timedelta(seconds=30)
    changed = await publish_if_changed(redis_client, "np-test", "T", "A", now=now2)
    assert changed is False

    raw = await redis_client.get(state_key("np-test"))
    data = json.loads(raw.decode())
    assert data["at"] == now1.isoformat()


async def test_at_preserved_across_refreshes(redis_client: Redis) -> None:
    first_now = datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC)
    await publish_if_changed(redis_client, "np-test", "X", "Y", now=first_now)

    for offset in (10, 20, 30, 45):
        later = first_now + timedelta(seconds=offset)
        await publish_if_changed(redis_client, "np-test", "X", "Y", now=later)

    raw = await redis_client.get(state_key("np-test"))
    data = json.loads(raw.decode())
    assert data["at"] == first_now.isoformat()


async def test_at_updates_when_track_changes(redis_client: Redis) -> None:
    t0 = datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC)
    await publish_if_changed(redis_client, "np-test", "Track1", "A", now=t0)

    t1 = t0 + timedelta(seconds=45)
    changed = await publish_if_changed(redis_client, "np-test", "Track2", "A", now=t1)
    assert changed is True

    raw = await redis_client.get(state_key("np-test"))
    data = json.loads(raw.decode())
    assert data["title"] == "Track2"
    assert data["at"] == t1.isoformat()


async def test_corrupt_json_triggers_rewrite(redis_client: Redis) -> None:
    await redis_client.set(state_key("np-test"), b"not-valid-json{{{")
    changed = await publish_if_changed(redis_client, "np-test", "T", "A")
    assert changed is True
    raw = await redis_client.get(state_key("np-test"))
    data = json.loads(raw.decode())
    assert data["title"] == "T"


async def test_ttl_renewed_on_no_change(redis_client: Redis) -> None:
    await publish_if_changed(redis_client, "np-test", "T", "A")
    await redis_client.expire(state_key("np-test"), 30)  # shorten
    ttl_before = await redis_client.ttl(state_key("np-test"))
    await publish_if_changed(redis_client, "np-test", "T", "A")
    ttl_after = await redis_client.ttl(state_key("np-test"))
    assert ttl_after > ttl_before
