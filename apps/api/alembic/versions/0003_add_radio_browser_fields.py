"""add Radio-Browser metadata columns to stations

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-25

Persists Radio-Browser fields that the sync flow already consumes but
hasn't been storing: clickcount, votes, changeuuid, lastlocalchecktime.
Also adds an empty `click_trend` column (default 0) reserved for a
future history-based implementation; computing it requires a separate
clickcount-history table that is out of scope for this migration.

All columns are added with safe defaults so the migration is non-blocking
on the existing 1355 rows. compute_quality_score now has access to real
popularity data instead of collapsing to 0.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stations",
        sa.Column("clickcount", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "stations",
        sa.Column("votes", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "stations",
        sa.Column(
            "last_changeuuid", postgresql.UUID(as_uuid=True), nullable=True,
        ),
    )
    op.add_column(
        "stations",
        sa.Column(
            "last_local_checktime", sa.TIMESTAMP(timezone=True), nullable=True,
        ),
    )
    op.add_column(
        "stations",
        sa.Column("click_trend", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("idx_stations_clickcount", "stations", ["clickcount"])
    op.create_index("idx_stations_votes", "stations", ["votes"])


def downgrade() -> None:
    op.drop_index("idx_stations_votes", table_name="stations")
    op.drop_index("idx_stations_clickcount", table_name="stations")
    op.drop_column("stations", "click_trend")
    op.drop_column("stations", "last_local_checktime")
    op.drop_column("stations", "last_changeuuid")
    op.drop_column("stations", "votes")
    op.drop_column("stations", "clickcount")
