from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class RecEventIn(BaseModel):
    station_id: uuid.UUID
    event_type: Literal["impression", "click"]
    slot: int | None = Field(default=None, ge=0, le=100)


class RecEventsRequest(BaseModel):
    """Body for ``POST /api/v1/recs/events``.

    Las impresiones se mandan en batch (una request por render del módulo);
    los clicks de uno en uno. Identidad: JWT gana sobre client_id, igual
    que en el registro de plays.
    """

    surface: Literal["home_for_you", "station_similar"]
    variant: str | None = Field(default=None, max_length=40)
    client_id: uuid.UUID | None = None
    events: list[RecEventIn] = Field(min_length=1, max_length=50)


class RecEventsResponse(BaseModel):
    inserted: int
