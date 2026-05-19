"""add hidden column to stations

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-19

Adds a soft-hide flag on stations so editorial-spammy entries can be
filtered out of public listings without losing the underlying data or
breaking direct slug access. The default is `false` so applying this
migration is a no-op for behavior; the data flip happens in a follow-up
ticket.

Partial index `idx_stations_hidden_curated` matches the shape of the
public list and home-featured queries (`hidden = false`, often combined
with `curated = true`). Reverse-direction queries fall back to the
existing indexes.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stations",
        sa.Column(
            "hidden",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_index(
        "idx_stations_hidden_curated",
        "stations",
        ["hidden", "curated"],
        postgresql_where=sa.text("hidden = false"),
    )


def downgrade() -> None:
    op.drop_index("idx_stations_hidden_curated", table_name="stations")
    op.drop_column("stations", "hidden")
