from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


_INSERT_USER = text(
    """
    INSERT INTO station_plays (station_id, user_id)
    VALUES (:sid, :uid)
    ON CONFLICT (user_id, station_id, ((played_at AT TIME ZONE 'UTC')::date))
    WHERE user_id IS NOT NULL
    DO NOTHING
    RETURNING id
    """,
)

_INSERT_CLIENT = text(
    """
    INSERT INTO station_plays (station_id, client_id)
    VALUES (:sid, :cid)
    ON CONFLICT (client_id, station_id, ((played_at AT TIME ZONE 'UTC')::date))
    WHERE client_id IS NOT NULL
    DO NOTHING
    RETURNING id
    """,
)


async def register_play(
    session: AsyncSession,
    *,
    station_id: uuid.UUID,
    user_id: uuid.UUID | None,
    client_id: uuid.UUID | None,
) -> bool:
    """Insert one play event. Returns True if newly inserted, False if dedup'd.

    The caller guarantees XOR(user_id, client_id) — the DB enforces it
    again with a check constraint as a safety net. Daily dedup is done
    via partial unique indices keyed on UTC date.
    """
    if user_id is not None:
        result = await session.execute(
            _INSERT_USER, {"sid": str(station_id), "uid": str(user_id)},
        )
    else:
        result = await session.execute(
            _INSERT_CLIENT, {"sid": str(station_id), "cid": str(client_id)},
        )
    inserted = result.first() is not None
    await session.commit()
    return inserted
