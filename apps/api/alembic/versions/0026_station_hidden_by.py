"""stations.hidden_by: quién ocultó una emisora

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-06

Fase 3a de la clasificación (ADR 012): el clasificador oculta las emisoras rechazadas con el
mismo ``hidden`` que ya respetan todas las consultas. Para poder reponerlas cuando se
reclasifican sin tocar nunca lo que ocultó otra vía (spam, decisión manual), se marca el origen:
``hidden_by = 'classifier'``. Una fila oculta con ``hidden_by`` NULL no la toca el clasificador.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | Sequence[str] | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stations", sa.Column("hidden_by", sa.String(length=16), nullable=True))
    op.create_check_constraint(
        "chk_stations_hidden_by",
        "stations",
        "hidden_by IS NULL OR hidden_by IN ('classifier')",
    )


def downgrade() -> None:
    op.drop_constraint("chk_stations_hidden_by", "stations", type_="check")
    op.drop_column("stations", "hidden_by")
