from __future__ import annotations

import uuid

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
