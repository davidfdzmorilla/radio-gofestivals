"""stations.updated_at solo avanza con cambios de contenido

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-09

El trigger original (``set_updated_at``, ``BEFORE UPDATE``) ponía ``updated_at = now()`` en
cualquier UPDATE, aunque no cambiase ningún valor. El health-check (cada 6 h), el cálculo de
tendencias de clics y el de ``quality_score`` reescriben todas las filas, así que ``updated_at``
valía "hoy" para todo el catálogo y no servía como ``lastmod`` del sitemap (ADR 015).

Ahora avanza solo si cambia una columna de contenido (lo que ve el visitante o decide la
indexación): slug, nombre, web, logos, país, ciudad, idioma, geo, ``hidden``, ``status`` y
``class_state``. Las operativas (``last_check_*``, ``quality_score``, ``click_trend``,
``clickcount``, votos, ``rb_tags``, ``electronic_score``...) ya no lo mueven. Un ``updated_at``
fijado explícitamente por el que escribe (el admin) se respeta.

Los géneros viven en ``station_genres``: un trigger ``AFTER`` toca la emisora cuando se añade,
quita o cambia un género. No se rellena el pasado: no hay forma de saber cuándo cambió cada
emisora, y el sitemap solo emite ``lastmod`` para cambios posteriores a esta migración.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0027"
down_revision: str | Sequence[str] | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONTENT_COLUMNS = (
    "slug",
    "name",
    "homepage_url",
    "favicon_url",
    "logo_hash",
    "country_code",
    "city",
    "language",
    "geo",
    "hidden",
    "status",
    "class_state",
)


def _row(alias: str) -> str:
    return "ROW(" + ", ".join(f"{alias}.{c}" for c in _CONTENT_COLUMNS) + ")"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION set_station_updated_at() RETURNS trigger AS $$
        BEGIN
            IF {_row("NEW")} IS DISTINCT FROM {_row("OLD")} THEN
                NEW.updated_at := now();
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_stations_updated_at ON stations")
    op.execute(
        """
        CREATE TRIGGER trg_stations_updated_at
            BEFORE UPDATE ON stations
            FOR EACH ROW EXECUTE FUNCTION set_station_updated_at()
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION touch_station_from_genres() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                UPDATE stations SET updated_at = now() WHERE id = NEW.station_id;
            ELSIF TG_OP = 'DELETE' THEN
                UPDATE stations SET updated_at = now() WHERE id = OLD.station_id;
            ELSIF NEW.genre_id IS DISTINCT FROM OLD.genre_id
                  OR NEW.station_id IS DISTINCT FROM OLD.station_id THEN
                UPDATE stations SET updated_at = now()
                 WHERE id IN (OLD.station_id, NEW.station_id);
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_station_genres_touch_station
            AFTER INSERT OR UPDATE OR DELETE ON station_genres
            FOR EACH ROW EXECUTE FUNCTION touch_station_from_genres()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_station_genres_touch_station ON station_genres")
    op.execute("DROP FUNCTION IF EXISTS touch_station_from_genres()")
    op.execute("DROP TRIGGER IF EXISTS trg_stations_updated_at ON stations")
    op.execute(
        """
        CREATE TRIGGER trg_stations_updated_at
            BEFORE UPDATE ON stations
            FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """
    )
    op.execute("DROP FUNCTION IF EXISTS set_station_updated_at()")
