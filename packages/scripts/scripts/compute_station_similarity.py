"""compute-station-similarity · top-K vecinos por emisora.

Corazón del sistema de recomendación (docs/recommendations-plan.md §3.1):

    sim(a,b) = 0.50·cos_géneros + 0.25·jaccard_coplay
             + 0.15·[mismo idioma] + 0.10·[mismo país]

- Vector de géneros por emisora desde station_genres.confidence, con
  propagación 0.5 al género padre (tech-house ≈ deep-house vía house).
- Jaccard de co-oyentes sobre station_plays (ventana de retención, 90d),
  identidad = COALESCE(user_id, client_id), mínimo 3 co-oyentes.
- Se guardan los top-K=20 vecinos con sim >= 0.15; solo destinos
  active + visibles + quality_score >= 30. Los componentes van
  desglosados (genre_score, coplay_score) para re-pesar sin recomputar.

La tabla se regenera entera en una transacción (DELETE + INSERT):
con miles de emisoras son ~20·N filas, trivial para el batch nocturno.
"""

from __future__ import annotations

import asyncio
import math
import uuid
from collections import defaultdict
from typing import TYPE_CHECKING

import typer
from sqlalchemy import text

from scripts.db import make_engine, make_sessionmaker
from scripts.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

log = get_logger("compute_station_similarity")
app = typer.Typer(help="radio.gofestivals · compute station-station similarity")

W_GENRE = 0.50
W_COPLAY = 0.25
W_LANGUAGE = 0.15
W_COUNTRY = 0.10
PARENT_PROPAGATION = 0.5
TOP_K = 20
MIN_SCORE = 0.15
MIN_DEST_QUALITY = 30
MIN_CO_LISTENERS = 3
INSERT_BATCH = 500


async def _load_stations(
    session: AsyncSession,
) -> dict[uuid.UUID, tuple[str | None, str | None, int]]:
    """id -> (country_code, language, quality_score) de emisoras recomendables."""
    rows = (
        await session.execute(
            text(
                """
                SELECT id, country_code, language, quality_score
                FROM stations
                WHERE status = 'active' AND NOT hidden
                """,
            ),
        )
    ).all()
    return {
        uuid.UUID(str(r[0])): (
            str(r[1]) if r[1] is not None else None,
            str(r[2]) if r[2] is not None else None,
            int(r[3]) if r[3] is not None else 0,
        )
        for r in rows
    }


async def _load_genre_vectors(
    session: AsyncSession,
) -> dict[uuid.UUID, dict[int, float]]:
    """Vector disperso género->peso por emisora, con propagación al padre."""
    parent_of: dict[int, int | None] = {
        int(r[0]): (int(r[1]) if r[1] is not None else None)
        for r in (await session.execute(text("SELECT id, parent_id FROM genres"))).all()
    }
    vectors: dict[uuid.UUID, dict[int, float]] = defaultdict(dict)
    rows = (
        await session.execute(
            text("SELECT station_id, genre_id, confidence FROM station_genres"),
        )
    ).all()
    for r in rows:
        sid = uuid.UUID(str(r[0]))
        gid = int(r[1])
        weight = int(r[2]) / 100.0
        vec = vectors[sid]
        vec[gid] = max(vec.get(gid, 0.0), weight)
        parent = parent_of.get(gid)
        if parent is not None:
            propagated = PARENT_PROPAGATION * weight
            vec[parent] = max(vec.get(parent, 0.0), propagated)
    return vectors


async def _load_coplay(
    session: AsyncSession,
) -> tuple[dict[uuid.UUID, int], dict[tuple[uuid.UUID, uuid.UUID], int]]:
    """(oyentes únicos por emisora, co-oyentes por par ordenado a<b)."""
    rows = (
        await session.execute(
            text(
                """
                SELECT COALESCE(user_id, client_id) AS ident, station_id
                FROM station_plays
                GROUP BY ident, station_id
                """,
            ),
        )
    ).all()
    by_identity: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    listeners: dict[uuid.UUID, int] = defaultdict(int)
    for r in rows:
        ident = uuid.UUID(str(r[0]))
        sid = uuid.UUID(str(r[1]))
        by_identity[ident].append(sid)
        listeners[sid] += 1

    co_counts: dict[tuple[uuid.UUID, uuid.UUID], int] = defaultdict(int)
    for stations_of_ident in by_identity.values():
        stations_sorted = sorted(stations_of_ident, key=lambda s: s.bytes)
        for i, a in enumerate(stations_sorted):
            for b in stations_sorted[i + 1 :]:
                co_counts[(a, b)] += 1
    return dict(listeners), dict(co_counts)


def _cosine(a: dict[int, float], b: dict[int, float]) -> float:
    if not a or not b:
        return 0.0
    if len(b) < len(a):
        a, b = b, a
    dot = sum(w * b[g] for g, w in a.items() if g in b)
    if dot == 0.0:
        return 0.0
    norm_a = math.sqrt(sum(w * w for w in a.values()))
    norm_b = math.sqrt(sum(w * w for w in b.values()))
    return dot / (norm_a * norm_b)


def _candidate_pairs(
    stations: dict[uuid.UUID, tuple[str | None, str | None, int]],
    vectors: dict[uuid.UUID, dict[int, float]],
    co_counts: dict[tuple[uuid.UUID, uuid.UUID], int],
) -> set[tuple[uuid.UUID, uuid.UUID]]:
    """Pares que comparten >=1 género (índice invertido) o tienen co-oyentes.

    El resto tendría sim < umbral salvo bonus idioma+país, que por sí solos
    (0.25) superan 0.15 — por eso idioma+país solo cuentan cuando hay señal
    de contenido o de co-escucha.
    """
    by_genre: dict[int, list[uuid.UUID]] = defaultdict(list)
    for sid, vec in vectors.items():
        if sid not in stations:
            continue
        for gid in vec:
            by_genre[gid].append(sid)

    pair_keys: set[tuple[uuid.UUID, uuid.UUID]] = set()
    for members in by_genre.values():
        members_sorted = sorted(members, key=lambda s: s.bytes)
        for i, a in enumerate(members_sorted):
            for b in members_sorted[i + 1 :]:
                pair_keys.add((a, b))
    for a, b in co_counts:
        if a in stations and b in stations:
            pair_keys.add((a, b))
    return pair_keys


def compute_similarities(
    stations: dict[uuid.UUID, tuple[str | None, str | None, int]],
    vectors: dict[uuid.UUID, dict[int, float]],
    listeners: dict[uuid.UUID, int],
    co_counts: dict[tuple[uuid.UUID, uuid.UUID], int],
) -> list[tuple[uuid.UUID, uuid.UUID, float, float, float, int]]:
    """Filas (station_id, similar_id, score, genre_score, coplay_score, rank)."""
    neighbors: dict[uuid.UUID, list[tuple[float, float, float, uuid.UUID]]] = defaultdict(list)
    for a, b in _candidate_pairs(stations, vectors, co_counts):
        cos = _cosine(vectors.get(a, {}), vectors.get(b, {}))
        co = co_counts.get((a, b), 0)
        jac = 0.0
        if co >= MIN_CO_LISTENERS:
            union = listeners.get(a, 0) + listeners.get(b, 0) - co
            if union > 0:
                jac = co / union
        if cos == 0.0 and jac == 0.0:
            continue
        country_a, lang_a, _ = stations[a]
        country_b, lang_b, _ = stations[b]
        same_lang = 1.0 if lang_a is not None and lang_a == lang_b else 0.0
        same_country = 1.0 if country_a is not None and country_a == country_b else 0.0
        score = min(
            1.0,
            W_GENRE * cos + W_COPLAY * jac + W_LANGUAGE * same_lang + W_COUNTRY * same_country,
        )
        if score < MIN_SCORE:
            continue
        if stations[b][2] >= MIN_DEST_QUALITY:
            neighbors[a].append((score, cos, jac, b))
        if stations[a][2] >= MIN_DEST_QUALITY:
            neighbors[b].append((score, cos, jac, a))

    out: list[tuple[uuid.UUID, uuid.UUID, float, float, float, int]] = []
    for sid, cands in neighbors.items():
        cands.sort(key=lambda c: (-c[0], c[3].bytes))
        for rank, (score, cos, jac, other) in enumerate(cands[:TOP_K], start=1):
            out.append((sid, other, round(score, 6), round(cos, 6), round(jac, 6), rank))
    return out


async def _write(
    session: AsyncSession,
    rows: list[tuple[uuid.UUID, uuid.UUID, float, float, float, int]],
) -> None:
    await session.execute(text("DELETE FROM station_similarity"))
    insert = text(
        """
        INSERT INTO station_similarity
            (station_id, similar_station_id, score, genre_score, coplay_score, rank)
        VALUES (:sid, :other, :score, :genre, :coplay, :rank)
        """,
    )
    for i in range(0, len(rows), INSERT_BATCH):
        chunk = rows[i : i + INSERT_BATCH]
        await session.execute(
            insert,
            [
                {
                    "sid": str(sid),
                    "other": str(other),
                    "score": score,
                    "genre": genre,
                    "coplay": coplay,
                    "rank": rank,
                }
                for sid, other, score, genre, coplay, rank in chunk
            ],
        )


async def run_compute(
    maker: async_sessionmaker[AsyncSession],
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """Compute and (unless dry_run) persist the similarity table."""
    async with maker() as session:
        stations = await _load_stations(session)
        vectors = await _load_genre_vectors(session)
        listeners, co_counts = await _load_coplay(session)
        rows = compute_similarities(stations, vectors, listeners, co_counts)
        stats = {
            "stations": len(stations),
            "with_genres": sum(1 for s in stations if vectors.get(s)),
            "coplay_pairs": len(co_counts),
            "similarity_rows": len(rows),
        }
        if dry_run:
            log.info("similarity_dry_run", **stats)
            return stats
        await _write(session, rows)
        await session.commit()
        log.info("similarity_done", **stats)
        return stats


async def _run(*, dry_run: bool) -> None:
    engine = make_engine()
    maker = make_sessionmaker(engine)
    try:
        await run_compute(maker, dry_run=dry_run)
    finally:
        await engine.dispose()


@app.command()
def run(
    dry_run: bool = typer.Option(default=False, help="Don't write."),
) -> None:
    """Recompute station_similarity (top-K vecinos por emisora)."""
    asyncio.run(_run(dry_run=dry_run))


if __name__ == "__main__":
    app()
