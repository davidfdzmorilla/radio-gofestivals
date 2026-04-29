from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class DashboardKpis(BaseModel):
    stations_active: int
    stations_curated: int
    stations_broken: int
    avg_quality_active: float


class QualityBucket(BaseModel):
    bucket: str
    count: int


class GenreCount(BaseModel):
    name: str
    count: int


class CountryCount(BaseModel):
    country_code: str
    count: int


class ActivityEntry(BaseModel):
    id: int
    decision: str
    station_id: uuid.UUID
    station_name: str | None
    station_slug: str | None
    admin_email: str | None
    notes: str | None
    created_at: datetime


class DashboardStats(BaseModel):
    kpis: DashboardKpis
    quality_distribution: list[QualityBucket]
    top_genres_curated: list[GenreCount]
    top_countries: list[CountryCount]
    recent_activity: list[ActivityEntry]
