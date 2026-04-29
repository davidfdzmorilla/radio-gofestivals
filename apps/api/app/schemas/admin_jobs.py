from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class JobCreateRequest(BaseModel):
    command: str
    params: dict[str, Any] | None = None


class JobOut(BaseModel):
    id: int
    command: str
    params_json: dict[str, Any] | None
    status: str
    result_json: dict[str, Any] | None
    stderr_tail: str | None
    started_at: datetime | None
    finished_at: datetime | None
    admin_id: uuid.UUID
    admin_email: str | None
    created_at: datetime


class JobListPage(BaseModel):
    items: list[JobOut]
    total: int
    page: int
    size: int
    pages: int


class CatalogEntry(BaseModel):
    command: str
    label: str
    description: str
    timeout: int
    params_schema: dict[str, Any]
