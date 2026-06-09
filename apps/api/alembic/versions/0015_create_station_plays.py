"""create station_plays + local_plays_total counter

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-09

First half of Fase B (own play tracking). Adds:

  - station_plays: append-only event log. Each row carries either a
    user_id (logged-in user) or a client_id (anonymous UUID from
    localStorage), never both, never neither — enforced by an XOR
    check constraint.
  - Two partial unique indices encoding the rate limit "1 play per
    identity per station per UTC day". Used by INSERT ... ON CONFLICT
    in the play registration path.
  - stations.local_plays_total: denormalized total play counter,
    maintained by an AFTER INSERT/DELETE trigger so the read path
    stays O(1). Reset to 0 on this migration; backfill is the trigger
    itself, going forward.

The 7-day rolling window for ranking is computed at query time in B5
(no separate column for it — keeps this PR small).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "station_plays",
        sa.Column(
            "id", sa.BigInteger(), primary_key=True, autoincrement=True,
        ),
        sa.Column(
            "station_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "played_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "(user_id IS NULL) <> (client_id IS NULL)",
            name="chk_plays_identity_xor",
        ),
    )
    op.create_index(
        "idx_plays_station_played_at",
        "station_plays",
        ["station_id", "played_at"],
    )
    # The UTC-pinned date expression is IMMUTABLE, which is required for
    # unique expression indices. `played_at::date` would be STABLE
    # (session-tz dependent) and Postgres refuses it on unique indices.
    op.execute(
        "CREATE UNIQUE INDEX idx_plays_user_station_day "
        "ON station_plays(user_id, station_id, ((played_at AT TIME ZONE 'UTC')::date)) "
        "WHERE user_id IS NOT NULL",
    )
    op.execute(
        "CREATE UNIQUE INDEX idx_plays_client_station_day "
        "ON station_plays(client_id, station_id, ((played_at AT TIME ZONE 'UTC')::date)) "
        "WHERE client_id IS NOT NULL",
    )

    op.add_column(
        "stations",
        sa.Column(
            "local_plays_total",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.execute(
        """
        CREATE FUNCTION inc_station_plays_total() RETURNS trigger AS $$
        BEGIN
          UPDATE stations
          SET local_plays_total = local_plays_total + 1
          WHERE id = NEW.station_id;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """,
    )
    op.execute(
        """
        CREATE FUNCTION dec_station_plays_total() RETURNS trigger AS $$
        BEGIN
          -- GREATEST guards against negative drift from manual edits or
          -- races. Counter is a hint for ranking; off-by-one is acceptable.
          UPDATE stations
          SET local_plays_total = GREATEST(0, local_plays_total - 1)
          WHERE id = OLD.station_id;
          RETURN OLD;
        END;
        $$ LANGUAGE plpgsql;
        """,
    )
    op.execute(
        "CREATE TRIGGER trg_station_plays_inc "
        "AFTER INSERT ON station_plays "
        "FOR EACH ROW EXECUTE FUNCTION inc_station_plays_total()",
    )
    op.execute(
        "CREATE TRIGGER trg_station_plays_dec "
        "AFTER DELETE ON station_plays "
        "FOR EACH ROW EXECUTE FUNCTION dec_station_plays_total()",
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_station_plays_dec ON station_plays",
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_station_plays_inc ON station_plays",
    )
    op.execute("DROP FUNCTION IF EXISTS dec_station_plays_total()")
    op.execute("DROP FUNCTION IF EXISTS inc_station_plays_total()")
    op.drop_column("stations", "local_plays_total")
    op.execute("DROP INDEX IF EXISTS idx_plays_client_station_day")
    op.execute("DROP INDEX IF EXISTS idx_plays_user_station_day")
    op.drop_index(
        "idx_plays_station_played_at", table_name="station_plays",
    )
    op.drop_table("station_plays")
