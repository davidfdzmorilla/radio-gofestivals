from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class NowPlayingEntry(BaseModel):
    title: str | None
    artist: str | None
    captured_at: datetime


class StationGenreRef(BaseModel):
    slug: str
    name: str
    color_hex: str


class StationSummary(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    country_code: str | None
    city: str | None
    codec: str | None
    bitrate: int | None
    curated: bool
    quality_score: int
    genres: list[str] = Field(default_factory=list)


class StationDetail(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    homepage_url: str | None
    country_code: str | None
    city: str | None
    codec: str | None
    bitrate: int | None
    language: str | None
    curated: bool
    quality_score: int
    status: str
    genres: list[StationGenreRef] = Field(default_factory=list)
    now_playing: list[NowPlayingEntry] = Field(default_factory=list)


class StationsPage(BaseModel):
    items: list[StationSummary]
    total: int
    page: int
    size: int
    pages: int


class NearbyStation(StationSummary):
    distance_km: float
