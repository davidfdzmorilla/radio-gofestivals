"""add station logos (favicon_url, logo_hash, station_logos)

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-05

Logos reales de emisoras (ADR 011). Radio-Browser trae un `favicon` por emisora en
hosts de terceros: no se sirve tal cual. El job `fetch-logos` lo descarga, lo
valida y guarda dos copias WebP propias en `station_logos`.

- ``stations.favicon_url``: URL de origen del logo (la rellena `rb_sync`).
- ``stations.logo_hash``: hash del logo ya procesado, copiado de `station_logos`
  para que los listados sepan si pedir el logo sin hacer JOIN. NULL = sin logo.
- ``station_logos``: imagen procesada (bytea) y estado del último intento.

Las tres adiciones son NULLables o tabla nueva: ninguna consulta SQL raw existente
sobre `stations` se rompe. El autogenerado propuso además borrar índices reales de
`stations` y las tablas del geocodificador de PostGIS (deriva entre el esquema SQL
inicial y los modelos): se descartó a mano, esta migración solo hace lo de arriba.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | Sequence[str] | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stations", sa.Column("favicon_url", sa.Text(), nullable=True))
    op.add_column("stations", sa.Column("logo_hash", sa.String(length=16), nullable=True))
    op.create_table(
        "station_logos",
        sa.Column("station_id", sa.UUID(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("content_hash", sa.String(length=16), nullable=True),
        sa.Column("data_sm", sa.LargeBinary(), nullable=True),
        sa.Column("data_lg", sa.LargeBinary(), nullable=True),
        sa.Column("attempts", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('ok', 'failed', 'rejected')",
            name="ck_station_logos_status",
        ),
        sa.ForeignKeyConstraint(
            ["station_id"],
            ["stations.id"],
            name="fk_station_logos_stations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("station_id"),
    )
    op.create_index(
        "idx_station_logos_status_retry",
        "station_logos",
        ["status", "next_retry_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_station_logos_status_retry", table_name="station_logos")
    op.drop_table("station_logos")
    op.drop_column("stations", "logo_hash")
    op.drop_column("stations", "favicon_url")
