"""initial schema from infra/sql/schema.sql

Revision ID: 0001
Revises:
Create Date: 2026-04-21

Esta migración ejecuta `infra/sql/schema.sql` como SQL crudo. Razón:
- `schema.sql` se declara fuente de verdad del schema inicial en su cabecera,
  y docker-compose lo monta en `/docker-entrypoint-initdb.d/` como fallback
  para DBs frescas sin alembic. Mantener una única fuente evita divergencia.
- Traducir ~230 líneas (extensiones PostGIS, enums, triggers plpgsql, seeds)
  a operaciones alembic solo aportaría duplicación hasta la migración 0002.
- Idempotencia: si `stations` ya existe (p.ej. porque initdb.d ya corrió
  el schema), esta migración se marca como aplicada sin reejecutar.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _find_schema_sql() -> Path:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[4] / "infra" / "sql" / "schema.sql",
        Path("/workspace/infra/sql/schema.sql"),
        Path("/app/infra/sql/schema.sql"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    searched = "\n  ".join(str(c) for c in candidates)
    msg = f"No encuentro infra/sql/schema.sql. Buscado en:\n  {searched}"
    raise FileNotFoundError(msg)


def upgrade() -> None:
    conn = op.get_bind()
    already = conn.execute(sa.text("SELECT to_regclass('public.stations')")).scalar()
    if already is not None:
        return
    schema_sql = _find_schema_sql().read_text(encoding="utf-8")
    conn.exec_driver_sql(schema_sql)


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql(
        """
        DROP TABLE IF EXISTS curation_log CASCADE;
        DROP TABLE IF EXISTS admins CASCADE;
        DROP TABLE IF EXISTS festival_stations CASCADE;
        DROP TABLE IF EXISTS now_playing CASCADE;
        DROP TABLE IF EXISTS station_genres CASCADE;
        DROP TABLE IF EXISTS stations CASCADE;
        DROP TABLE IF EXISTS genres CASCADE;
        DROP FUNCTION IF EXISTS set_updated_at() CASCADE;
        DROP TYPE IF EXISTS curation_decision;
        DROP TYPE IF EXISTS festival_link_type;
        DROP TYPE IF EXISTS station_status;
        """
    )
