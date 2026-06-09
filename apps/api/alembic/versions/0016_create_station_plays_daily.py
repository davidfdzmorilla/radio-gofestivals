"""create station_plays_daily aggregate

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-09

Daily aggregate that lets the retention job (B4) compact ``station_plays``
older than 90 days into one row per (station, UTC day). The detailed
event row gets deleted; the aggregate preserves the count for any
"historical totals" use case without keeping per-listener PII around
past the retention window.

Schema:
    station_plays_daily(station_id, day, plays)
PRIMARY KEY (station_id, day) is what the upsert keys on. The day-only
index supports a future "plays from last N days summed up" query that
spans the boundary between live and aggregated data.

Note on counters: the AFTER DELETE trigger on station_plays decrements
stations.local_plays_total when retention deletes the source rows. The
counter effectively becomes "plays in retention window" once any
retention pass has run. Documented in the script that does the work;
re-introducing an all-time counter is a future ticket if needed.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "station_plays_daily",
        sa.Column(
            "station_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("plays", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint(
            "station_id", "day", name="pk_station_plays_daily",
        ),
        sa.CheckConstraint("plays >= 0", name="chk_plays_daily_nonneg"),
    )
    op.create_index(
        "idx_plays_daily_day",
        "station_plays_daily",
        ["day"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_plays_daily_day", table_name="station_plays_daily",
    )
    op.drop_table("station_plays_daily")
