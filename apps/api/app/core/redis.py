from __future__ import annotations

from typing import TYPE_CHECKING

from redis.asyncio import Redis

if TYPE_CHECKING:
    from app.core.config import Settings

_client: Redis[str] | None = None


def init_redis(settings: Settings) -> Redis[str]:
    global _client  # noqa: PLW0603
    _client = Redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    return _client


async def close_redis() -> None:
    global _client  # noqa: PLW0603
    if _client is not None:
        await _client.aclose()  # type: ignore[attr-defined]
    _client = None


def get_redis() -> Redis[str]:
    if _client is None:
        msg = "Redis client no inicializado. ¿Olvidaste llamar init_redis en el lifespan?"
        raise RuntimeError(msg)
    return _client
