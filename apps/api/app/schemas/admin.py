from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class AdminLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class AccessToken(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime


class AdminMe(BaseModel):
    id: uuid.UUID
    email: EmailStr
    name: str | None
    last_login_at: datetime | None


class CurationRequest(BaseModel):
    decision: Literal["approve", "reject", "reclassify"]
    genre_ids: list[int] = Field(default_factory=list)
    quality_score: int | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=500)


class StationGenreConfidence(BaseModel):
    genre_id: int
    slug: str
    name: str
    confidence: int
    source: str


class StationPending(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    stream_url: str | None
    country_code: str | None
    city: str | None
    codec: str | None
    bitrate: int | None
    quality_score: int
    created_at: datetime
    last_sync_at: datetime | None
    has_geo: bool
    genres: list[StationGenreConfidence]


class StationPendingPage(BaseModel):
    items: list[StationPending]
    total: int
    page: int
    size: int
    pages: int


class GenreCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=60, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1, max_length=100)
    parent_id: int | None = None
    color_hex: str = Field(default="#8B4EE8", pattern=r"^#[0-9A-Fa-f]{6}$")
    sort_order: int = Field(default=100, ge=0, le=10_000)
    description: str | None = Field(default=None, max_length=500)


class GenreUpdate(BaseModel):
    slug: str | None = Field(default=None, min_length=2, max_length=60, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str | None = Field(default=None, min_length=1, max_length=100)
    parent_id: int | None = None
    color_hex: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    description: str | None = Field(default=None, max_length=500)


class GenreOut(BaseModel):
    id: int
    slug: str
    name: str
    parent_id: int | None
    color_hex: str
    sort_order: int
    description: str | None


class CurateResponse(BaseModel):
    station_id: uuid.UUID
    status: str
    curated: bool
    log_id: int


class StreamRef(BaseModel):
    """Lightweight reference used in admin list rows."""

    id: uuid.UUID
    url: str
    codec: str | None
    bitrate: int | None


class StationListItem(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    status: str
    curated: bool
    country_code: str | None
    quality_score: int
    primary_stream: StreamRef | None
    stream_count: int
    genre_count: int
    created_at: datetime
    last_sync_at: datetime | None


class StationListPage(BaseModel):
    items: list[StationListItem]
    total: int
    page: int
    size: int
    pages: int


class StreamDetail(BaseModel):
    id: uuid.UUID
    url: str
    codec: str | None
    bitrate: int | None
    format: str | None
    is_primary: bool
    status: str
    failed_checks: int
    last_error: str | None
    last_check_at: datetime | None


class AuditEntry(BaseModel):
    id: int
    admin_email: str
    decision: str
    notes: str | None
    created_at: datetime


class StationAdminDetail(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    status: str
    curated: bool
    country_code: str | None
    city: str | None
    language: str | None
    homepage_url: str | None
    quality_score: int
    clickcount: int
    votes: int
    click_trend: Decimal
    failed_checks: int
    last_error: str | None
    last_check_at: datetime | None
    last_sync_at: datetime | None
    created_at: datetime
    streams: list[StreamDetail] = Field(default_factory=list)
    genres: list[StationGenreConfidence] = Field(default_factory=list)
    audit: list[AuditEntry] = Field(default_factory=list)


class StationUpdate(BaseModel):
    """PATCH /admin/stations/{id} payload. All fields optional.

    Status is restricted to admin-controllable transitions; `pending` and
    `duplicate` are excluded because they are owned by the sync/dedupe
    pipelines, not by manual decisions.
    """

    curated: bool | None = None
    status: Literal["active", "broken", "inactive"] | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9-]*$",
    )
    genre_ids: list[int] | None = None
    notes: str | None = Field(default=None, max_length=500)
