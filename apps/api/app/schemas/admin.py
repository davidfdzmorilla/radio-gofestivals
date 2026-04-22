from __future__ import annotations

import uuid
from datetime import datetime
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
    stream_url: str
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
