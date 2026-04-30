from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class PromotePrimaryResponse(BaseModel):
    promoted_stream_id: uuid.UUID
    demoted_stream_id: uuid.UUID | None
    station_id: uuid.UUID


class BulkStatusChangeRequest(BaseModel):
    station_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    new_status: Literal["inactive"]
    reason: str | None = Field(default=None, max_length=200)


class BulkStatusChangeResponse(BaseModel):
    affected: int
    skipped: int
    station_ids_affected: list[uuid.UUID]
