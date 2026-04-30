from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def add_vote(
    session: AsyncSession,
    user_id: uuid.UUID,
    station_id: uuid.UUID,
) -> tuple[bool, int]:
    """Idempotent vote. Returns (newly_voted, votes_local_after).

    On the first vote, increments stations.votes_local atomically. On
    subsequent calls (conflict), only re-reads the counter.
    """
    inserted = (
        await session.execute(
            text(
                """
                INSERT INTO user_votes (user_id, station_id)
                VALUES (:uid, :sid)
                ON CONFLICT (user_id, station_id) DO NOTHING
                RETURNING user_id
                """,
            ),
            {"uid": str(user_id), "sid": str(station_id)},
        )
    ).first()

    if inserted is not None:
        new_count = (
            await session.execute(
                text(
                    """
                    UPDATE stations
                    SET votes_local = votes_local + 1
                    WHERE id = :sid
                    RETURNING votes_local
                    """,
                ),
                {"sid": str(station_id)},
            )
        ).scalar_one()
        return True, int(new_count)

    current = (
        await session.execute(
            text(
                "SELECT votes_local FROM stations WHERE id = :sid",
            ),
            {"sid": str(station_id)},
        )
    ).scalar_one_or_none()
    return False, int(current) if current is not None else 0


async def remove_vote(
    session: AsyncSession,
    user_id: uuid.UUID,
    station_id: uuid.UUID,
) -> tuple[bool, int]:
    """Remove a vote. Returns (was_removed, votes_local_after).

    Decrements the counter only when a row was actually deleted, with a
    GREATEST(0, …) guard so we never go negative.
    """
    deleted = (
        await session.execute(
            text(
                """
                DELETE FROM user_votes
                WHERE user_id = :uid AND station_id = :sid
                RETURNING user_id
                """,
            ),
            {"uid": str(user_id), "sid": str(station_id)},
        )
    ).first()

    if deleted is not None:
        new_count = (
            await session.execute(
                text(
                    """
                    UPDATE stations
                    SET votes_local = GREATEST(votes_local - 1, 0)
                    WHERE id = :sid
                    RETURNING votes_local
                    """,
                ),
                {"sid": str(station_id)},
            )
        ).scalar_one()
        return True, int(new_count)

    current = (
        await session.execute(
            text("SELECT votes_local FROM stations WHERE id = :sid"),
            {"sid": str(station_id)},
        )
    ).scalar_one_or_none()
    return False, int(current) if current is not None else 0


async def has_voted(
    session: AsyncSession,
    user_id: uuid.UUID,
    station_id: uuid.UUID,
) -> bool:
    row = (
        await session.execute(
            text(
                """
                SELECT 1 FROM user_votes
                WHERE user_id = :uid AND station_id = :sid
                """,
            ),
            {"uid": str(user_id), "sid": str(station_id)},
        )
    ).first()
    return row is not None


async def get_voted_station_ids(
    session: AsyncSession,
    user_id: uuid.UUID,
    station_ids: list[uuid.UUID],
) -> set[uuid.UUID]:
    if not station_ids:
        return set()
    rows = (
        await session.execute(
            text(
                """
                SELECT station_id FROM user_votes
                WHERE user_id = :uid
                  AND station_id = ANY(CAST(:ids AS uuid[]))
                """,
            ),
            {
                "uid": str(user_id),
                "ids": [str(s) for s in station_ids],
            },
        )
    ).all()
    return {uuid.UUID(str(r[0])) for r in rows}
