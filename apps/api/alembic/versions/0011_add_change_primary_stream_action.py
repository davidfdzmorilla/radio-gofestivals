"""add change_primary_stream to curation_decision enum

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-29

Extends the curation_decision enum so promote-primary actions can be
recorded in curation_log alongside the existing toggle_curated /
edit_metadata / change_status events.

Downgrade is intentionally a no-op: Postgres does not support DROP VALUE
on an enum without recreating the type.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE curation_decision ADD VALUE IF NOT EXISTS 'change_primary_stream'",
    )


def downgrade() -> None:
    pass
