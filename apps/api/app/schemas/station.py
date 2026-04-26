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


class StationStreamRef(BaseModel):
    id: uuid.UUID
    url: str
    codec: str | None
    bitrate: int | None
    format: str | None
    is_primary: bool


class StationSummary(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    country_code: str | None
    city: str | None
    curated: bool
    quality_score: int
    genres: list[str] = Field(default_factory=list)
    primary_stream: StationStreamRef | None = None


class StationDetail(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    homepage_url: str | None
    country_code: str | None
    city: str | None
    language: str | None
    curated: bool
    quality_score: int
    status: str
    genres: list[StationGenreRef] = Field(default_factory=list)
    streams: list[StationStreamRef] = Field(default_factory=list)
    now_playing: list[NowPlayingEntry] = Field(default_factory=list)


class StationsPage(BaseModel):
    items: list[StationSummary]
    total: int
    page: int
    size: int
    pages: int


class NearbyStation(StationSummary):
    distance_km: float
