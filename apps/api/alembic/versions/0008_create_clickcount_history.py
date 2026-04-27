"""create station_clickcount_history + promote click_trend to NUMERIC

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-27

Adds the daily clickcount-snapshot table that backs the 7-day trend
computation, and promotes stations.click_trend from INTEGER to
NUMERIC(10,4) so the log-ratio result keeps decimal precision.

The trend is informational and does not enter the quality_score formula.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "stations",
        "click_trend",
        type_=sa.Numeric(10, 4),
        server_default="0.0000",
        existing_type=sa.Integer(),
        existing_nullable=False,
        postgresql_using="click_trend::numeric(10,4)",
    )

    op.create_table(
        "station_clickcount_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "station_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("clickcount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "recorded_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_clickhist_station_id",
        "station_clickcount_history",
        ["station_id"],
    )
    op.create_index(
        "idx_clickhist_recorded_at",
        "station_clickcount_history",
        [sa.text("recorded_at DESC")],
    )
    # One snapshot per station per UTC day. The expression is wrapped with
    # `AT TIME ZONE 'UTC'` because Postgres's date() on a timestamptz is
    # not IMMUTABLE (depends on session timezone) and would be rejected.
    # Upsert target: `ON CONFLICT (station_id, ((recorded_at AT TIME ZONE
    # 'UTC')::date))` — the expression must match exactly.
    op.execute(
        "CREATE UNIQUE INDEX uq_clickhist_station_day "
        "ON station_clickcount_history "
        "(station_id, ((recorded_at AT TIME ZONE 'UTC')::date))",
    )


def downgrade() -> None:
    op.drop_index(
        "uq_clickhist_station_day", table_name="station_clickcount_history",
    )
    op.drop_index(
        "idx_clickhist_recorded_at", table_name="station_clickcount_history",
    )
    op.drop_index(
        "idx_clickhist_station_id", table_name="station_clickcount_history",
    )
    op.drop_table("station_clickcount_history")

    op.alter_column(
        "stations",
        "click_trend",
        type_=sa.Integer(),
        server_default="0",
        existing_type=sa.Numeric(10, 4),
        existing_nullable=False,
        postgresql_using="click_trend::integer",
    )
