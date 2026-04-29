from __future__ import annotations

import math
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def create_job(
    session: AsyncSession,
    *,
    command: str,
    params_json: dict[str, Any] | None,
    admin_id: uuid.UUID,
) -> dict[str, Any]:
    row = (
        await session.execute(
            text(
                """
                INSERT INTO admin_jobs
                    (command, params_json, status, admin_id)
                VALUES
                    (:command, CAST(:params AS jsonb), 'pending', :admin_id)
                RETURNING id, command, params_json, status, result_json,
                          stderr_tail, started_at, finished_at,
                          admin_id, created_at
                """,
            ),
            {
                "command": command,
                "params": _to_json(params_json),
                "admin_id": str(admin_id),
            },
        )
    ).first()
    assert row is not None
    return _row_to_dict(row)


async def list_jobs(
    session: AsyncSession,
    *,
    page: int,
    size: int,
    status: str | None = None,
) -> tuple[list[dict[str, Any]], int, int]:
    where = []
    params: dict[str, object] = {"limit": size, "offset": (page - 1) * size}
    if status:
        where.append("j.status = :status")
        params["status"] = status
    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    total = int(
        (
            await session.execute(
                text(
                    f"SELECT COUNT(*) FROM admin_jobs j {where_clause}",  # noqa: S608
                ),
                params,
            )
        ).scalar_one(),
    )

    rows = (
        await session.execute(
            text(
                f"""
                SELECT j.id, j.command, j.params_json, j.status,
                       j.result_json, j.stderr_tail,
                       j.started_at, j.finished_at,
                       j.admin_id, j.created_at,
                       a.email AS admin_email
                FROM admin_jobs j
                LEFT JOIN admins a ON a.id = j.admin_id
                {where_clause}
                ORDER BY j.created_at DESC, j.id DESC
                LIMIT :limit OFFSET :offset
                """,  # noqa: S608
            ),
            params,
        )
    ).all()

    items = [_row_to_dict(r) for r in rows]
    pages = max(1, math.ceil(total / size)) if total else 0
    return items, total, pages


async def get_job(
    session: AsyncSession, job_id: int,
) -> dict[str, Any] | None:
    row = (
        await session.execute(
            text(
                """
                SELECT j.id, j.command, j.params_json, j.status,
                       j.result_json, j.stderr_tail,
                       j.started_at, j.finished_at,
                       j.admin_id, j.created_at,
                       a.email AS admin_email
                FROM admin_jobs j
                LEFT JOIN admins a ON a.id = j.admin_id
                WHERE j.id = :id
                """,
            ),
            {"id": job_id},
        )
    ).first()
    if row is None:
        return None
    return _row_to_dict(row)


def _to_json(value: dict[str, Any] | None) -> str | None:
    if value is None:
        return None
    import json

    return json.dumps(value)


def _row_to_dict(row: Any) -> dict[str, Any]:  # noqa: ANN401
    mapping = row._mapping  # noqa: SLF001
    return {
        "id": int(mapping["id"]),
        "command": str(mapping["command"]),
        "params_json": mapping["params_json"],
        "status": str(mapping["status"]),
        "result_json": mapping["result_json"],
        "stderr_tail": mapping["stderr_tail"],
        "started_at": mapping["started_at"],
        "finished_at": mapping["finished_at"],
        "admin_id": uuid.UUID(str(mapping["admin_id"])),
        "created_at": mapping["created_at"],
        "admin_email": (
            str(mapping["admin_email"])
            if "admin_email" in mapping and mapping["admin_email"] is not None
            else None
        ),
    }
