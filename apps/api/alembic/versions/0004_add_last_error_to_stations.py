"""add last_error and last_check_at to stations

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-26

The previous health-check (HEAD against Icecast/Shoutcast) marked ~29%
of curated stations as broken with no diagnostic trail. The rewrite
to GET-with-Icy-MetaData needs places to record both *why* a check
failed and *when* it last ran (`last_check_ok` only flips on success,
which is useless for diagnosing repeat failures).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stations", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column(
        "stations",
        sa.Column("last_check_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stations", "last_check_at")
    op.drop_column("stations", "last_error")
