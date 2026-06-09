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


_MERGE_DROP_CONFLICTS = text(
    """
    DELETE FROM station_plays anon
    WHERE anon.client_id = :cid AND anon.user_id IS NULL
      AND EXISTS (
        SELECT 1 FROM station_plays u
        WHERE u.user_id = :uid AND u.station_id = anon.station_id
          AND (u.played_at AT TIME ZONE 'UTC')::date
              = (anon.played_at AT TIME ZONE 'UTC')::date
      )
    RETURNING 1
    """,
)

_MERGE_UPDATE = text(
    """
    UPDATE station_plays SET user_id = :uid, client_id = NULL
    WHERE client_id = :cid AND user_id IS NULL
    RETURNING 1
    """,
)


async def merge_anon_plays_to_user(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    client_id: uuid.UUID,
) -> tuple[int, int]:
    """Reassign anonymous plays from ``client_id`` to ``user_id``.

    Rows that would collide with an existing user_id row on the same
    (station, UTC day) are deleted (the user already has the per-day
    play, so the data point survives). The remaining rows are updated
    in place — no INSERT/DELETE fires on those, so the denormalized
    counter stays consistent on the updated rows. The DELETE trigger
    decrements the counter for the dropped conflicts.

    Returns (merged, dropped_conflicts).
    """
    dropped = (
        await session.execute(
            _MERGE_DROP_CONFLICTS,
            {"cid": str(client_id), "uid": str(user_id)},
        )
    ).all()
    merged = (
        await session.execute(
            _MERGE_UPDATE,
            {"cid": str(client_id), "uid": str(user_id)},
        )
    ).all()
    await session.commit()
    return len(merged), len(dropped)


async def export_user_plays(
    session: AsyncSession, user_id: uuid.UUID,
) -> list[dict[str, object]]:
    """Return every play row attributed to ``user_id``, joined with the
    station for an informative GDPR dump (slug + name).
    """
    import uuid as _uuid  # noqa: PLC0415

    rows = (
        await session.execute(
            text(
                """
                SELECT s.id AS station_id, s.slug, s.name, p.played_at
                FROM station_plays p
                JOIN stations s ON s.id = p.station_id
                WHERE p.user_id = :uid
                ORDER BY p.played_at DESC
                """,
            ),
            {"uid": str(user_id)},
        )
    ).all()
    return [
        {
            "station_id": _uuid.UUID(str(r[0])),
            "station_slug": str(r[1]),
            "station_name": str(r[2]),
            "played_at": r[3],
        }
        for r in rows
    ]


async def erase_user_plays(
    session: AsyncSession, user_id: uuid.UUID,
) -> int:
    """Delete every play row attributed to ``user_id``.

    Returns the row count. The DELETE trigger keeps ``local_plays_total``
    consistent on the affected stations.
    """
    result = await session.execute(
        text("DELETE FROM station_plays WHERE user_id = :uid RETURNING 1"),
        {"uid": str(user_id)},
    )
    count = len(result.all())
    await session.commit()
    return count
