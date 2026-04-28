"""extend curation_decision enum with admin metadata actions

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-28

Adds three values to the curation_decision enum so that the existing
curation_log table can record granular admin actions performed via the
new /admin/stations endpoints (Tier 1):

  - toggle_curated  → admin flipped the `curated` flag
  - edit_metadata   → admin edited name, slug, or genre_ids
  - change_status   → admin changed status (active/broken/inactive)

We extend the existing enum instead of introducing a new audit_log table
to keep the audit trail in a single place. The naming overlap with the
original curation flow (approve/reject/reclassify) is acceptable: every
value still represents an admin decision against a station, recorded with
admin_id + station_id + notes + timestamp.

Note: ALTER TYPE ADD VALUE works inside a transaction in Postgres 12+ as
long as the new value is not consumed within the same transaction. This
migration only adds values; no INSERTs use them, so it is safe.

The downgrade is intentionally a no-op: Postgres does not support removing
enum values without recreating the type and rewriting every row that
references it. The new values are harmless to leave in place if a
downgrade is ever needed.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE curation_decision ADD VALUE IF NOT EXISTS 'toggle_curated'",
    )
    op.execute(
        "ALTER TYPE curation_decision ADD VALUE IF NOT EXISTS 'edit_metadata'",
    )
    op.execute(
        "ALTER TYPE curation_decision ADD VALUE IF NOT EXISTS 'change_status'",
    )


def downgrade() -> None:
    # Postgres enum values cannot be dropped without recreating the type.
    # The added values are harmless if left in place after a downgrade.
    pass
