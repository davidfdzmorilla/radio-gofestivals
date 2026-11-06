"""stations.class_evidence: huella de la evidencia con la que se clasificó

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-06

Fase 2 de la clasificación: un veredicto del segundo clasificador (``class_source = 'llm'``) solo
vale mientras no cambie la evidencia (nombre y tags). ``class_evidence`` guarda su huella para no
volver a preguntar por lo ya decidido y para que el recálculo de reglas no pise un veredicto
vigente.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | Sequence[str] | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stations", sa.Column("class_evidence", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("stations", "class_evidence")
