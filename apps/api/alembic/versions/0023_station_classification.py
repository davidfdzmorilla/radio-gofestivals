"""stations: tags crudos de Radio-Browser y clasificación "¿es electrónica?"

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-06

Fase 1 de la clasificación automática del catálogo. Hoy una emisora entra por buscar
tags ambiguos (progressive, minimal, ambient, house…) y no se guarda la evidencia con la
que se decidió, así que no se puede reclasificar sin volver a Radio-Browser.

- ``rb_tags``: tags crudos normalizados de Radio-Browser (NULL = aún no recogidos;
  array vacío = recogidos y la emisora no trae ninguno).
- ``electronic_score`` (0-100), ``class_state`` (accepted/review/rejected),
  ``class_reason``, ``class_source`` (rule/llm/manual) y ``classified_at``: veredicto del
  clasificador. En esta fase es solo informativo: nada lee estas columnas para ocultar.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023"
down_revision: str | Sequence[str] | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stations", sa.Column("rb_tags", postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column("stations", sa.Column("electronic_score", sa.SmallInteger(), nullable=True))
    op.add_column("stations", sa.Column("class_state", sa.String(length=16), nullable=True))
    op.add_column("stations", sa.Column("class_reason", sa.Text(), nullable=True))
    op.add_column("stations", sa.Column("class_source", sa.String(length=16), nullable=True))
    op.add_column(
        "stations",
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "chk_stations_electronic_score",
        "stations",
        "electronic_score IS NULL OR electronic_score BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        "chk_stations_class_state",
        "stations",
        "class_state IS NULL OR class_state IN ('accepted', 'review', 'rejected')",
    )
    op.create_check_constraint(
        "chk_stations_class_source",
        "stations",
        "class_source IS NULL OR class_source IN ('rule', 'llm', 'manual')",
    )


def downgrade() -> None:
    op.drop_constraint("chk_stations_class_source", "stations", type_="check")
    op.drop_constraint("chk_stations_class_state", "stations", type_="check")
    op.drop_constraint("chk_stations_electronic_score", "stations", type_="check")
    op.drop_column("stations", "classified_at")
    op.drop_column("stations", "class_source")
    op.drop_column("stations", "class_reason")
    op.drop_column("stations", "class_state")
    op.drop_column("stations", "electronic_score")
    op.drop_column("stations", "rb_tags")
