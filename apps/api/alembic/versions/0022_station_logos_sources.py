"""station_logos: con qué URLs se intentó y de dónde salió el logo

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-05

Los logos pasan a tener una segunda fuente (ADR 011, addendum): si el favicon de
Radio-Browser no sirve, `fetch-logos` lee la web de la emisora y usa su
apple-touch-icon o `<link rel=icon>`. Para detectar cuándo reintentar hace falta saber
QUÉ URLs había al intentarlo, no solo la del icono final:

- ``favicon_seen`` / ``homepage_seen``: `stations.favicon_url` y `stations.homepage_url`
  en el momento del último intento. Si cambian, la emisora vuelve a la cola.
- ``source_kind``: `favicon` u `homepage`, de dónde salió el logo (`source_url` pasa a ser
  la URL del icono, que ya no tiene por qué coincidir con `favicon_url`).

Relleno de las filas existentes (todas vienen de favicon): `favicon_seen = source_url`,
`source_kind = 'favicon'`. `homepage_seen` solo se rellena en las que ya tienen logo
(`ok`): así no se vuelven a descargar, mientras que las `failed`/`rejected` quedan con
`homepage_seen` NULL, distinto de la web actual, y entran en la cola para probar la
nueva escalera (favicon -> icono de la web).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | Sequence[str] | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("station_logos", sa.Column("favicon_seen", sa.Text(), nullable=True))
    op.add_column("station_logos", sa.Column("homepage_seen", sa.Text(), nullable=True))
    op.add_column("station_logos", sa.Column("source_kind", sa.String(length=16), nullable=True))
    op.create_check_constraint(
        "ck_station_logos_source_kind",
        "station_logos",
        "source_kind IS NULL OR source_kind IN ('favicon', 'homepage')",
    )
    op.execute("UPDATE station_logos SET favicon_seen = source_url, source_kind = 'favicon'")
    op.execute(
        """
        UPDATE station_logos l SET homepage_seen = s.homepage_url
        FROM stations s
        WHERE s.id = l.station_id AND l.status = 'ok'
        """,
    )


def downgrade() -> None:
    op.drop_constraint("ck_station_logos_source_kind", "station_logos", type_="check")
    op.drop_column("station_logos", "source_kind")
    op.drop_column("station_logos", "homepage_seen")
    op.drop_column("station_logos", "favicon_seen")
