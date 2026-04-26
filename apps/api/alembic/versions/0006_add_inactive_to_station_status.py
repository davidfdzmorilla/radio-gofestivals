"""add 'inactive' to station_status enum

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-26

The brand/streams refactor flips formerly-'duplicate' rows to 'inactive'
once their stream has been attached to the brand owner. The enum was
missing that value.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE station_status ADD VALUE IF NOT EXISTS 'inactive'",
        )


def downgrade() -> None:
    # Postgres has no `ALTER TYPE ... DROP VALUE`. Same pattern as 0002.
    pass
