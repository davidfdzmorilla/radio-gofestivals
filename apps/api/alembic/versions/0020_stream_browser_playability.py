"""add browser-playability signals to station_streams

Revision ID: 0020
Revises: 0019
Create Date: 2026-06-16

El health-check en Python (httpx) daba por viva una emisora que el
navegador no puede reproducir: el chequeo ignora CORS, mixed-content
(https→http) y certificados TLS inválidos (reintenta con verify=False).
Resultado: ~8% del catálogo activo marcado OK pero inreproducible en el
`<audio>` del player.

Dos señales nuevas, nullable (NULL = aún no chequeado por la versión
CORS-aware):
- ``cors_ok``: el stream devuelve Access-Control-Allow-Origin permisivo.
  No condiciona la reproducción (el player ya no exige crossOrigin), pero
  permite diagnóstico y, en el futuro, re-habilitar el analyzer real.
- ``browser_playable``: TLS válido y sin redirección a http. Cuando es
  False, el stream es inreproducible en un sitio https y el health-check
  lo trata como fallo (mecanismo de 3 strikes ya existente).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | Sequence[str] | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "station_streams",
        sa.Column("cors_ok", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "station_streams",
        sa.Column("browser_playable", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("station_streams", "browser_playable")
    op.drop_column("station_streams", "cors_ok")
