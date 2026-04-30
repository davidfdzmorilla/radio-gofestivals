from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class StreamNotFoundError(Exception):
    """Raised when the target stream id does not exist."""


class AlreadyPrimaryError(Exception):
    """Raised when the target stream is already the primary."""


async def promote_stream_to_primary(
    session: AsyncSession,
    *,
    stream_id: uuid.UUID,
    admin_id: uuid.UUID,
) -> dict[str, Any]:
    """Promote a stream to primary, demoting the current primary atomically.

    Order matters: the table has a partial UNIQUE index
    (station_id WHERE is_primary=true), so we MUST demote first then
    promote, otherwise the UPDATE blows up with IntegrityError.
    """
    target = (
        await session.execute(
            text(
                """
                SELECT id, station_id, is_primary
                FROM station_streams
                WHERE id = :id
                """,
            ),
            {"id": str(stream_id)},
        )
    ).first()
    if target is None:
        raise StreamNotFoundError(str(stream_id))

    target_id = uuid.UUID(str(target[0]))
    station_id = uuid.UUID(str(target[1]))
    if bool(target[2]):
        raise AlreadyPrimaryError(str(stream_id))

    demoted_row = (
        await session.execute(
            text(
                """
                UPDATE station_streams
                SET is_primary = false, updated_at = now()
                WHERE station_id = :station_id
                  AND is_primary = true
                RETURNING id
                """,
            ),
            {"station_id": str(station_id)},
        )
    ).first()
    demoted_id: uuid.UUID | None = (
        uuid.UUID(str(demoted_row[0])) if demoted_row else None
    )

    await session.execute(
        text(
            """
            UPDATE station_streams
            SET is_primary = true, updated_at = now()
            WHERE id = :id
            """,
        ),
        {"id": str(target_id)},
    )

    notes = (
        f"Promoted stream {target_id} to primary"
        + (
            f" (demoted {demoted_id})"
            if demoted_id
            else " (no previous primary)"
        )
    )
    await session.execute(
        text(
            """
            INSERT INTO curation_log
                (admin_id, station_id, decision, notes)
            VALUES
                (:admin_id, :station_id,
                 CAST(:decision AS curation_decision), :notes)
            """,
        ),
        {
            "admin_id": str(admin_id),
            "station_id": str(station_id),
            "decision": "change_primary_stream",
            "notes": notes,
        },
    )

    await session.commit()
    return {
        "promoted_stream_id": target_id,
        "demoted_stream_id": demoted_id,
        "station_id": station_id,
    }


async def bulk_change_status(
    session: AsyncSession,
    *,
    station_ids: list[uuid.UUID],
    new_status: Literal["inactive"],
    reason: str | None,
    admin_id: uuid.UUID,
) -> dict[str, Any]:
    """Bulk transition stations to a new status.

    Currently only `inactive` is supported. Stations already in the
    target status are skipped (no audit entry, idempotent).
    """
    if not station_ids:
        raise ValueError("empty_station_ids")
    if len(station_ids) > 100:
        raise ValueError("too_many_stations")

    ids_str = [str(sid) for sid in station_ids]
    affected_rows = (
        await session.execute(
            text(
                """
                UPDATE stations
                SET status = CAST(:new_status AS station_status),
                    updated_at = now()
                WHERE id = ANY(CAST(:ids AS uuid[]))
                  AND status::text != :new_status
                RETURNING id
                """,
            ),
            {"new_status": new_status, "ids": ids_str},
        )
    ).all()
    affected_ids = [uuid.UUID(str(row[0])) for row in affected_rows]
    affected = len(affected_ids)
    skipped = len(station_ids) - affected

    if affected_ids:
        marker = (
            f"bulk_{new_status}:{affected}_stations"
            + (f":reason='{reason}'" if reason else "")
        )
        for sid in affected_ids:
            await session.execute(
                text(
                    """
                    INSERT INTO curation_log
                        (admin_id, station_id, decision, notes)
                    VALUES
                        (:admin_id, :station_id,
                         CAST(:decision AS curation_decision), :notes)
                    """,
                ),
                {
                    "admin_id": str(admin_id),
                    "station_id": str(sid),
                    "decision": "change_status",
                    "notes": marker,
                },
            )

    await session.commit()
    return {
        "affected": affected,
        "skipped": skipped,
        "station_ids_affected": affected_ids,
    }
