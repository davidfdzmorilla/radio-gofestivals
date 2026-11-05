from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    LargeBinary,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.station import Station


class StationLogo(Base):
    """Logo de una emisora, ya descargado y re-codificado a WebP (ADR 011).

    Nunca se sirve el archivo original de la fuente (host de un tercero): el job
    `fetch-logos` lo decodifica, lo valida y guarda DOS copias propias. `status`:
    `ok` (hay imagen), `failed` (descarga o decodificación fallida; se reintenta con
    backoff en `next_retry_at`) o `rejected` (imagen inservible, p. ej. SVG o menor de
    64 px; no se reintenta hasta que cambie la URL de origen).
    """

    __tablename__ = "station_logos"
    __table_args__ = (
        CheckConstraint("status IN ('ok', 'failed', 'rejected')", name="ck_station_logos_status"),
        Index("idx_station_logos_status_retry", "status", "next_retry_at"),
    )

    station_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stations.id", ondelete="CASCADE", name="fk_station_logos_stations"),
        primary_key=True,
    )
    # URL que se descargó; si `stations.favicon_url` cambia, el job vuelve a descargar.
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    # Hash corto del contenido: versiona la URL pública (caché inmutable) y da el ETag.
    content_hash: Mapped[str | None] = mapped_column(String(16), nullable=True)
    data_sm: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    data_lg: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    attempts: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    fetched_at: Mapped[datetime | None] = mapped_column(nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    station: Mapped[Station] = relationship("Station", back_populates="logo")
