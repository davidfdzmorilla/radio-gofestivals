from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis


STATE_KEY_PREFIX = "np:state:"
STATE_TTL_SECONDS = 120


def state_key(slug: str) -> str:
    return f"{STATE_KEY_PREFIX}{slug}"


async def publish_if_changed(
    redis: Redis[bytes],
    slug: str,
    title: str | None,
    artist: str | None,
    *,
    now: datetime | None = None,
) -> bool:
    """Escribe np:state:<slug> solo si title/artist cambiaron.

    Si no cambiaron, solo renueva TTL para que el `at` original (inicio
    de la canción) permanezca estable. Devuelve True si hubo cambio.
    """
    key = state_key(slug)
    current = await redis.get(key)
    if current is not None:
        try:
            raw = current.decode("utf-8") if isinstance(current, bytes) else current
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
            data = None
        if isinstance(data, dict) and data.get("title") == title and data.get("artist") == artist:
            await redis.expire(key, STATE_TTL_SECONDS)
            return False

    ts = (now or datetime.now(tz=UTC)).isoformat()
    payload = json.dumps(
        {"title": title, "artist": artist, "at": ts},
        ensure_ascii=False,
    )
    await redis.set(key, payload, ex=STATE_TTL_SECONDS)
    return True
