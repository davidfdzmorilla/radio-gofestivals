"""create user_refresh_tokens

Revision ID: 0018
Revises: 0017
Create Date: 2026-06-10

Sesiones con refresh token rotatorio (plan de mejoras B3): el access
token JWT pasa a vivir minutos en memoria del cliente, y la sesión la
sostiene un token opaco en cookie httpOnly. Aquí solo se guarda el
SHA-256 del token (el valor en claro nunca toca la DB).

``replaced_by_hash`` encadena las rotaciones: si alguien presenta un
token ya rotado (robo/replay), se revocan todas las sesiones del usuario.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018"
down_revision: str | Sequence[str] | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_refresh_tokens",
        sa.Column("token_hash", sa.Text(), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_refresh_user"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_hash", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_refresh_user", "user_refresh_tokens", ["user_id"])
    op.create_index("idx_refresh_expires", "user_refresh_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_index("idx_refresh_expires", table_name="user_refresh_tokens")
    op.drop_index("idx_refresh_user", table_name="user_refresh_tokens")
    op.drop_table("user_refresh_tokens")
