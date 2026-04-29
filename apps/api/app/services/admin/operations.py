from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from app.repos import admin_jobs as jobs_repo
from app.services.admin.operations_catalog import ALLOWED_COMMANDS

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CommandNotAllowedError(Exception):
    """Raised when the requested command is not in ALLOWED_COMMANDS."""


class InvalidParamsError(Exception):
    """Raised when params fail validation against the command's schema."""


async def enqueue_job(
    session: AsyncSession,
    *,
    admin_id: uuid.UUID,
    command: str,
    raw_params: dict[str, Any] | None,
) -> dict[str, Any]:
    if command not in ALLOWED_COMMANDS:
        raise CommandNotAllowedError(command)

    spec = ALLOWED_COMMANDS[command]
    params_model = spec["params_model"]

    try:
        validated = params_model(**(raw_params or {}))
    except ValidationError as exc:
        raise InvalidParamsError(str(exc)) from exc

    params_dict = validated.model_dump(exclude_none=True)
    job = await jobs_repo.create_job(
        session,
        command=command,
        params_json=params_dict or None,
        admin_id=admin_id,
    )
    await session.commit()
    return job
