from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis


async def check_rate_limit(
    redis: Redis[str],
    key: str,
    *,
    limit: int,
    window_seconds: int,
) -> tuple[bool, int]:
    bucket = f"rl:{key}"
    pipe = redis.pipeline()
    pipe.incr(bucket)
    pipe.expire(bucket, window_seconds, nx=True)
    count, _ = await pipe.execute()
    count_int = int(count)
    return count_int <= limit, count_int
