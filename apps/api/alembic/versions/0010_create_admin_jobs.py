"""create admin_jobs table for Tier 3 operations

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-29

Adds the admin_jobs table that backs the async execution of CLI
commands triggered from the admin UI (Tier 3 of admin-plan.md).

The API enqueues a job (status='pending'); a host cron worker calls
`run-pending-admin-jobs run` every minute, claims one job using
`FOR UPDATE SKIP LOCKED`, runs the corresponding command via
subprocess, and updates the row with the outcome.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_jobs",
        sa.Column(
            "id", sa.BigInteger(), primary_key=True, autoincrement=True,
        ),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("params_json", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("result_json", postgresql.JSONB(), nullable=True),
        sa.Column("stderr_tail", sa.Text(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "finished_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "admin_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("admins.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','success','failed','timeout')",
            name="admin_jobs_status_check",
        ),
    )
    op.create_index(
        "idx_admin_jobs_status_created",
        "admin_jobs",
        ["status", "created_at"],
    )
    op.create_index(
        "idx_admin_jobs_admin",
        "admin_jobs",
        ["admin_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_admin_jobs_admin", table_name="admin_jobs")
    op.drop_index("idx_admin_jobs_status_created", table_name="admin_jobs")
    op.drop_table("admin_jobs")
