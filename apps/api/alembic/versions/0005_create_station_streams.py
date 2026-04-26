"""create station_streams (split brand from technical variants)

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-26

Adds the station_streams table that holds N technical variants per
station (mp3 320, aac+ 64, opus 96, ...). Exactly one row per station
may carry is_primary=true, enforced by a partial unique index.

Also relaxes stations.stream_url to NULL: from this revision onward
rb_sync writes the stream URL exclusively into station_streams; the
legacy column survives for the duration of the backfill and is dropped
in 0006.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE stream_status AS ENUM ('active', 'broken', 'inactive')",
    )

    op.create_table(
        "station_streams",
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
        sa.Column("stream_url", sa.Text(), nullable=False),
        sa.Column("codec", sa.Text(), nullable=True),
        sa.Column("bitrate", sa.Integer(), nullable=True),
        sa.Column("format", sa.Text(), nullable=True),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "active", "broken", "inactive",
                name="stream_status",
                create_type=False,
            ),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "failed_checks",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "last_check_at", sa.TIMESTAMP(timezone=True), nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "idx_station_streams_station_id", "station_streams", ["station_id"],
    )
    op.create_index(
        "idx_station_streams_status", "station_streams", ["status"],
    )
    op.create_index(
        "uq_station_streams_station_url",
        "station_streams",
        ["station_id", "stream_url"],
        unique=True,
    )
    op.create_index(
        "uq_station_streams_one_primary",
        "station_streams",
        ["station_id"],
        unique=True,
        postgresql_where=sa.text("is_primary = true"),
    )

    op.execute(
        "ALTER TABLE stations ALTER COLUMN stream_url DROP NOT NULL",
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE stations ALTER COLUMN stream_url SET NOT NULL",
    )
    op.drop_index("uq_station_streams_one_primary", table_name="station_streams")
    op.drop_index("uq_station_streams_station_url", table_name="station_streams")
    op.drop_index("idx_station_streams_status", table_name="station_streams")
    op.drop_index("idx_station_streams_station_id", table_name="station_streams")
    op.drop_table("station_streams")
    op.execute("DROP TYPE stream_status")
