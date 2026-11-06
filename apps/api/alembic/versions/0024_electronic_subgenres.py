"""genres: subgéneros electrónicos que el catálogo ya trae y la taxonomía no tenía

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-06

El análisis de los tags de Radio-Browser del catálogo (2026-11-06) mostró 222 emisoras visibles
sin ningún género y muchos tags electrónicos sin destino: lounge (~90), jungle (~30),
synthwave, afro house, uk garage, nu disco, eurodance, IDM/experimental e industrial. Se añaden
como géneros propios (idempotente: ``ON CONFLICT (slug) DO NOTHING``, por si el admin ya los
creó). El padre se resuelve por slug y queda NULL si no existe en esa base (chill-out y dance
los creó el admin en prod; no están en el seed inicial).
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0024"
down_revision: str | Sequence[str] | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (slug, nombre, slug del padre, color, orden)
GENRES: tuple[tuple[str, str, str | None, str, int], ...] = (
    ("lounge", "Lounge", "chill-out", "#15A8DA", 110),
    ("jungle", "Jungle", "dnb", "#A61AA9", 120),
    ("synthwave", "Synthwave", None, "#E62DE9", 130),
    ("afro-house", "Afro House", "house", "#E62DE9", 140),
    ("uk-garage", "UK Garage", None, "#8B4EE8", 150),
    ("nu-disco", "Nu Disco", "house", "#E62DE9", 160),
    ("eurodance", "Eurodance", "dance", "#1CC1F9", 170),
    ("idm", "IDM & Experimental", None, "#15A8DA", 180),
    ("industrial", "Industrial", None, "#808080", 190),
)


def upgrade() -> None:
    for slug, name, parent, color, order in GENRES:
        op.execute(
            f"""
            INSERT INTO genres (slug, name, parent_id, color_hex, sort_order)
            VALUES (
                '{slug}', '{name}',
                {f"(SELECT id FROM genres WHERE slug = '{parent}')" if parent else "NULL"},
                '{color}', {order}
            )
            ON CONFLICT (slug) DO NOTHING
            """,  # noqa: S608
        )


def downgrade() -> None:
    slugs = ", ".join(f"'{g[0]}'" for g in GENRES)
    op.execute(f"DELETE FROM genres WHERE slug IN ({slugs})")  # noqa: S608
