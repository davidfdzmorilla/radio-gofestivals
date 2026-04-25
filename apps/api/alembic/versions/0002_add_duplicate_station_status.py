"""add 'duplicate' to station_status enum

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-25

Radio-Browser registers the same logical station N times with different
bitrate/codec/UUID combinations. Until we refactor to a stations +
station_streams split, dedup conservatively by marking redundant rows as
status='duplicate'. Public endpoints already filter status='active', so
adding the value is enough to hide them.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE must run outside a transaction in Postgres.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE station_status ADD VALUE IF NOT EXISTS 'duplicate'")


def downgrade() -> None:
    # Postgres has no `ALTER TYPE ... DROP VALUE`. Reverting would require
    # recreating the enum and rewriting every column referencing it. Since
    # 'duplicate' is additive and harmless when unused, we leave it in place
    # on downgrade.
    pass
