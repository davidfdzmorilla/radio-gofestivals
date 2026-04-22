from __future__ import annotations

import asyncio
import os

from redis.asyncio import Redis

from app.services.rate_limit import check_rate_limit


async def _fresh_redis() -> Redis[str]:
    return Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)


async def test_ttl_is_fixed_on_first_increment_only() -> None:
    redis = await _fresh_redis()
    try:
        await check_rate_limit(redis, "fixed-window-key", limit=100, window_seconds=10)
        first_ttl = await redis.ttl("rl:fixed-window-key")
        assert first_ttl > 0

        await asyncio.sleep(1.1)

        await check_rate_limit(redis, "fixed-window-key", limit=100, window_seconds=10)
        second_ttl = await redis.ttl("rl:fixed-window-key")

        assert second_ttl < first_ttl, (
            f"TTL no debe reiniciarse. first={first_ttl}, second={second_ttl}"
        )
    finally:
        await redis.delete("rl:fixed-window-key")
        await redis.aclose()


async def test_counter_increments_within_window() -> None:
    redis = await _fresh_redis()
    try:
        results = [
            await check_rate_limit(redis, "counter-key", limit=5, window_seconds=10)
            for _ in range(7)
        ]
        counts = [count for _, count in results]
        assert counts == [1, 2, 3, 4, 5, 6, 7]
        allowed_flags = [ok for ok, _ in results]
        assert allowed_flags == [True, True, True, True, True, False, False]
    finally:
        await redis.delete("rl:counter-key")
        await redis.aclose()
