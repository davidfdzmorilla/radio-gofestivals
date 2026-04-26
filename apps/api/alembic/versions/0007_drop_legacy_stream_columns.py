"""drop legacy stream_url, codec, bitrate from stations

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-26

After backfill into station_streams (migration 0005 + migrate-streams
script) and verification that API/frontend serve traffic from the new
relationship, drop the legacy per-station stream columns.

This migration is intentionally separate from 0005 so it can be
withheld until operator confirms playback works end-to-end.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("stations", "stream_url")
    op.drop_column("stations", "codec")
    op.drop_column("stations", "bitrate")


def downgrade() -> None:
    # Schema-only restore. Original data lives in station_streams; this
    # downgrade does not back-copy it.
    op.add_column("stations", sa.Column("bitrate", sa.Integer(), nullable=True))
    op.add_column("stations", sa.Column("codec", sa.Text(), nullable=True))
    op.add_column("stations", sa.Column("stream_url", sa.Text(), nullable=True))
