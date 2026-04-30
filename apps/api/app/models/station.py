from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from geoalchemy2 import Geography
from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    SmallInteger,
    Text,
)
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.genre import Genre
    from app.models.station_clickcount_history import StationClickcountHistory
    from app.models.station_stream import StationStream


station_status_enum = ENUM(
    "pending",
    "active",
    "broken",
    "rejected",
    "unsupported",
    "duplicate",
    "inactive",
    name="station_status",
    create_type=False,
)


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.uuid_generate_v4(),
    )
    rb_uuid: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=True,
    )
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # stream_url, codec, bitrate were moved to station_streams in migration
    # 0005. The columns are kept on the table only until 0007 drops them.
    homepage_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    country_code: Mapped[str | None] = mapped_column(CHAR(2), nullable=True)
    city: Mapped[str | None] = mapped_column(Text, nullable=True)
    geo: Mapped[str | None] = mapped_column(
        Geography(geometry_type="POINT", srid=4326),
        nullable=True,
    )
    language: Mapped[str | None] = mapped_column(Text, nullable=True)
    curated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quality_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=50)
    status: Mapped[str] = mapped_column(station_status_enum, nullable=False, default="pending")
    failed_checks: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    last_check_ok: Mapped[datetime | None] = mapped_column(nullable=True)
    last_check_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(nullable=True)
    clickcount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    votes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Local "like" count, driven by user_votes (separate from `votes` which
    # mirrors the Radio-Browser remote count via rb_sync).
    votes_local: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_changeuuid: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )
    last_local_checktime: Mapped[datetime | None] = mapped_column(nullable=True)
    # 7-day log-ratio of clickcount, computed nightly from
    # station_clickcount_history. Defaults to 0 until the 7th snapshot lands.
    click_trend: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, default=0,
    )
    source: Mapped[str] = mapped_column(Text, nullable=False, default="radio-browser")
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("quality_score BETWEEN 0 AND 100", name="chk_quality_score"),
        CheckConstraint("bitrate IS NULL OR bitrate > 0", name="chk_bitrate"),
    )

    genres: Mapped[list[Genre]] = relationship(
        "Genre",
        secondary="station_genres",
        lazy="selectin",
    )

    clickcount_history: Mapped[list[StationClickcountHistory]] = relationship(
        "StationClickcountHistory",
        back_populates="station",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    streams: Mapped[list[StationStream]] = relationship(
        "StationStream",
        back_populates="station",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="(StationStream.is_primary.desc(), StationStream.bitrate.desc())",
    )


class StationGenre(Base):
    __tablename__ = "station_genres"

    station_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stations.id", ondelete="CASCADE"),
        nullable=False,
    )
    genre_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("genres.id", ondelete="CASCADE"),
        nullable=False,
    )
    confidence: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=50)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    __table_args__ = (
        PrimaryKeyConstraint("station_id", "genre_id"),
        CheckConstraint("confidence BETWEEN 0 AND 100", name="chk_sg_confidence"),
    )


class NowPlaying(Base):
    __tablename__ = "now_playing"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    station_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stations.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    artist: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
