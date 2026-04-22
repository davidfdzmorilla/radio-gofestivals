from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        SmallInteger,
        ForeignKey("genres.id", ondelete="SET NULL"),
        nullable=True,
    )
    color_hex: Mapped[str] = mapped_column(Text, nullable=False, default="#8B4EE8")
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=100)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    parent: Mapped[Genre | None] = relationship("Genre", remote_side="Genre.id", backref="children")
