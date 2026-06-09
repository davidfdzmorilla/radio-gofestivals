from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class PlayRegisterRequest(BaseModel):
    """Body for ``POST /api/v1/stations/{slug}/play``.

    The ``client_id`` is the opaque UUID the client mints in localStorage
    on first play after consent (see web Cookies page). It is only
    consulted when the request carries no valid Authorization header — a
    logged-in user always identifies by ``user_id``.
    """

    client_id: uuid.UUID | None = None


class PlayRegisterResponse(BaseModel):
    accepted: bool
    deduplicated: bool


class MergePlaysRequest(BaseModel):
    """Body for ``POST /api/v1/me/plays/merge``."""

    client_id: uuid.UUID


class MergePlaysResponse(BaseModel):
    merged: int
    dropped_conflicts: int


class PlayExportItem(BaseModel):
    station_id: uuid.UUID
    station_slug: str
    station_name: str
    played_at: datetime


class UserExportInfo(BaseModel):
    id: uuid.UUID
    email: str
    created_at: datetime


class PlaysExportResponse(BaseModel):
    """GDPR Art. 15 dump scoped to the plays surface.

    The user's favorites and likes already have their own export-friendly
    endpoints (``/users/favorites``, ``/users/stations/{id}/like``); this
    payload intentionally stays focused on what the B2/B3 plays pipeline
    stored.
    """

    user: UserExportInfo
    plays: list[PlayExportItem]


class ErasePlaysResponse(BaseModel):
    erased: int
