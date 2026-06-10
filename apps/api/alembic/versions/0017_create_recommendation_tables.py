"""create recommendation tables (station_similarity, rec_events)

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-10

Sistema de recomendación (docs/recommendations-plan.md, ADR 004):

- ``station_similarity``: top-K vecinos por emisora precomputados cada
  noche por ``compute-station-similarity`` (coseno de géneros + Jaccard
  de co-oyentes + idioma + país). Los componentes se guardan desglosados
  (genre_score, coplay_score) para poder re-pesar el blend sin recomputar.
- ``rec_events``: impresiones y clicks del módulo de recomendaciones,
  con la misma identidad XOR user/client que station_plays. Sin esto el
  sistema no se puede evaluar (CTR, play-through, interleaving).

Además añade ``idx_plays_station_played`` sobre station_plays: las
queries de popularidad local (plays de los últimos 30 días por emisora)
del scoring on-the-fly filtran por station_id + played_at, y los índices
parciales de dedup existentes lideran por identidad, no por emisora.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "station_similarity",
        sa.Column(
            "station_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "stations.id", ondelete="CASCADE", name="fk_similarity_station",
            ),
            nullable=False,
        ),
        sa.Column(
            "similar_station_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "stations.id", ondelete="CASCADE", name="fk_similarity_similar_station",
            ),
            nullable=False,
        ),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("genre_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("coplay_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rank", sa.SmallInteger(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint(
            "station_id", "similar_station_id", name="pk_station_similarity",
        ),
        sa.CheckConstraint(
            "station_id <> similar_station_id", name="chk_similarity_not_self",
        ),
        sa.CheckConstraint(
            "score >= 0 AND score <= 1", name="chk_similarity_score",
        ),
    )
    op.create_index(
        "idx_station_similarity_lookup",
        "station_similarity",
        ["station_id", "rank"],
    )

    op.create_table(
        "rec_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "station_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "stations.id", ondelete="CASCADE", name="fk_rec_events_station",
            ),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_rec_events_user"),
            nullable=True,
        ),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("surface", sa.Text(), nullable=False),
        sa.Column("variant", sa.Text(), nullable=True),
        sa.Column("slot", sa.SmallInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "(user_id IS NULL) <> (client_id IS NULL)",
            name="chk_rec_events_identity",
        ),
        sa.CheckConstraint(
            "event_type IN ('impression', 'click')",
            name="chk_rec_events_type",
        ),
    )
    op.create_index(
        "idx_rec_events_station_created",
        "rec_events",
        ["station_id", "created_at"],
    )
    op.create_index("idx_rec_events_created", "rec_events", ["created_at"])

    # Popularidad local por emisora (plays últimos N días) para el scoring.
    op.create_index(
        "idx_plays_station_played",
        "station_plays",
        ["station_id", "played_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_plays_station_played", table_name="station_plays")
    op.drop_index("idx_rec_events_created", table_name="rec_events")
    op.drop_index("idx_rec_events_station_created", table_name="rec_events")
    op.drop_table("rec_events")
    op.drop_index("idx_station_similarity_lookup", table_name="station_similarity")
    op.drop_table("station_similarity")
