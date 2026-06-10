"""create email_verification_tokens

Revision ID: 0019
Revises: 0018
Create Date: 2026-06-10

Verificación de email (plan de mejoras B4): la columna
users.email_verified_at existía desde el MVP de usuarios pero nunca se
rellenaba. Tabla de tokens de un solo uso, espejo de
password_reset_tokens (mismo ciclo: emitir → email → consumir).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: str | Sequence[str] | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_verification_tokens",
        sa.Column(
            "token",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_emailverif_user"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_emailverif_user", "email_verification_tokens", ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_emailverif_user", table_name="email_verification_tokens")
    op.drop_table("email_verification_tokens")
