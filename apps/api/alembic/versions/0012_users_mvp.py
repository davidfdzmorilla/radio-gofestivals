"""users MVP: users + user_favorites + user_votes + reset tokens + votes_local

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-30

Creates the public-user system documented in docs/users-mvp-plan.md.

The `users` table is intentionally future-proof: optional username/bio/
avatar/is_public columns let us evolve into a social product without a
follow-up migration. Email uniqueness is partial (excludes soft-deleted
rows) so re-registration after account deletion is allowed.

`stations.votes_local` is a denormalized counter incremented/decremented
inside the same transaction as user_votes inserts/deletes, kept separate
from `stations.votes` (which still stores the Radio-Browser remote vote
count from rb_sync — public stat, not driven by this app).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("username", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "email_verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "deleted_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "uq_users_email",
        "users",
        ["email"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_users_username",
        "users",
        ["username"],
        unique=True,
        postgresql_where=sa.text(
            "deleted_at IS NULL AND username IS NOT NULL",
        ),
    )
    op.create_index(
        "idx_users_created_at",
        "users",
        [sa.text("created_at DESC")],
    )

    op.create_table(
        "user_favorites",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "station_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "station_id", name="pk_user_favorites",
        ),
    )
    op.create_index(
        "idx_user_favorites_user",
        "user_favorites",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_user_favorites_station",
        "user_favorites",
        ["station_id"],
    )

    op.create_table(
        "user_votes",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "station_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "station_id", name="pk_user_votes",
        ),
    )
    op.create_index(
        "idx_user_votes_station",
        "user_votes",
        ["station_id"],
    )

    op.create_table(
        "password_reset_tokens",
        sa.Column(
            "token",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "expires_at", sa.DateTime(timezone=True), nullable=False,
        ),
        sa.Column(
            "used_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_reset_tokens_user",
        "password_reset_tokens",
        ["user_id", sa.text("created_at DESC")],
    )

    op.add_column(
        "stations",
        sa.Column(
            "votes_local",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_index(
        "idx_stations_votes_local",
        "stations",
        [sa.text("votes_local DESC")],
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("idx_stations_votes_local", table_name="stations")
    op.drop_column("stations", "votes_local")
    op.drop_index(
        "idx_reset_tokens_user", table_name="password_reset_tokens",
    )
    op.drop_table("password_reset_tokens")
    op.drop_index("idx_user_votes_station", table_name="user_votes")
    op.drop_table("user_votes")
    op.drop_index(
        "idx_user_favorites_station", table_name="user_favorites",
    )
    op.drop_index(
        "idx_user_favorites_user", table_name="user_favorites",
    )
    op.drop_table("user_favorites")
    op.drop_index("idx_users_created_at", table_name="users")
    op.drop_index("uq_users_username", table_name="users")
    op.drop_index("uq_users_email", table_name="users")
    op.drop_table("users")
