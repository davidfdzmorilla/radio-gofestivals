"""eval-recommendations · evaluación offline del recomendador (solo lectura).

Hold-out temporal (docs/recommendations-plan.md §7): los plays anteriores
al corte son el contexto de cada identidad; los posteriores, los eventos a
predecir (solo emisoras NUEVAS para esa identidad). Para cada identidad
evaluable se construye un top-10 desde station_similarity (vecinos de sus
semillas, ponderados por plays) y se compara contra dos baselines de
popularidad: global y por país de la emisora más escuchada.

Limitación conocida (aceptable en MVP): station_similarity está computada
con TODOS los plays, incluidos los posteriores al corte — el Jaccard tiene
una fuga temporal leve. El coseno de géneros (50% del peso) no se ve
afectado. Para una eval estricta habría que recomputar la similitud solo
con el train; no compensa hasta tener volumen.

Métricas: recall@10 (modelo vs baselines) y coverage del catálogo curated
en las listas de vecinos. Salida: una línea JSON (consumible por jq).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections import defaultdict
from typing import TYPE_CHECKING

import typer
from sqlalchemy import text

from scripts.db import make_engine, make_sessionmaker
from scripts.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

log = get_logger("eval_recommendations")
app = typer.Typer(help="radio.gofestivals · offline eval del recomendador")

TOP_N = 10
MAX_SEEDS = 10


async def _load_plays(
    session: AsyncSession,
    *,
    cutoff_days: int,
) -> tuple[dict[uuid.UUID, dict[uuid.UUID, int]], dict[uuid.UUID, set[uuid.UUID]]]:
    """(train: identidad->{emisora: plays}, test: identidad->{emisoras nuevas})."""
    rows = (
        await session.execute(
            text(
                """
                SELECT COALESCE(user_id, client_id) AS ident, station_id,
                       COUNT(*) FILTER (
                           WHERE played_at < now() - make_interval(days => :d)
                       ) AS train_plays,
                       COUNT(*) FILTER (
                           WHERE played_at >= now() - make_interval(days => :d)
                       ) AS test_plays
                FROM station_plays
                GROUP BY ident, station_id
                """,
            ),
            {"d": cutoff_days},
        )
    ).all()
    train: dict[uuid.UUID, dict[uuid.UUID, int]] = defaultdict(dict)
    test: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for r in rows:
        ident = uuid.UUID(str(r[0]))
        sid = uuid.UUID(str(r[1]))
        train_n, test_n = int(r[2]), int(r[3])
        if train_n > 0:
            train[ident][sid] = train_n
        elif test_n > 0:
            test[ident].add(sid)  # solo emisoras NUEVAS post-corte
    return train, test


async def _load_neighbors(
    session: AsyncSession,
) -> dict[uuid.UUID, list[tuple[uuid.UUID, float]]]:
    rows = (
        await session.execute(
            text(
                """
                SELECT station_id, similar_station_id, score
                FROM station_similarity
                ORDER BY station_id, rank
                """,
            ),
        )
    ).all()
    out: dict[uuid.UUID, list[tuple[uuid.UUID, float]]] = defaultdict(list)
    for r in rows:
        out[uuid.UUID(str(r[0]))].append((uuid.UUID(str(r[1])), float(r[2])))
    return dict(out)


def _recommend(
    seeds: dict[uuid.UUID, int],
    neighbors: dict[uuid.UUID, list[tuple[uuid.UUID, float]]],
) -> list[uuid.UUID]:
    top_seeds = sorted(seeds, key=lambda s: (-seeds[s], s.bytes))[:MAX_SEEDS]
    max_plays = max(seeds[s] for s in top_seeds)
    scores: dict[uuid.UUID, float] = {}
    for seed in top_seeds:
        weight = seeds[seed] / max_plays
        for cand, sim in neighbors.get(seed, []):
            if cand in seeds:
                continue
            scores[cand] = max(scores.get(cand, 0.0), weight * sim)
    ranked = sorted(scores, key=lambda c: (-scores[c], c.bytes))
    return ranked[:TOP_N]


async def _run(*, cutoff_days: int) -> None:
    engine = make_engine()
    maker = make_sessionmaker(engine)
    try:
        async with maker() as session:
            train, test = await _load_plays(session, cutoff_days=cutoff_days)
            neighbors = await _load_neighbors(session)

            # Baselines de popularidad sobre el train
            global_pop: dict[uuid.UUID, int] = defaultdict(int)
            for seeds in train.values():
                for sid, n in seeds.items():
                    global_pop[sid] += n
            top_global = sorted(global_pop, key=lambda s: -global_pop[s])[:TOP_N]

            country_rows = (
                await session.execute(
                    text("SELECT id, country_code FROM stations"),
                )
            ).all()
            country_of = {uuid.UUID(str(r[0])): (str(r[1]) if r[1] else None) for r in country_rows}
            pop_by_country: dict[str, dict[uuid.UUID, int]] = defaultdict(
                lambda: defaultdict(int),
            )
            for sid, n in global_pop.items():
                cc = country_of.get(sid)
                if cc:
                    pop_by_country[cc][sid] += n

            evaluated = hits_model = hits_global = hits_country = 0
            for ident, new_stations in test.items():
                ident_seeds = train.get(ident)
                if not ident_seeds or not new_stations:
                    continue
                evaluated += 1
                recs = set(_recommend(ident_seeds, neighbors))
                if recs & new_stations:
                    hits_model += 1
                if set(top_global) & new_stations:
                    hits_global += 1
                fav_country = country_of.get(
                    max(ident_seeds, key=lambda s: ident_seeds[s]),
                )
                top_cc = (
                    sorted(
                        pop_by_country.get(fav_country, {}),
                        key=lambda s: -pop_by_country[fav_country or ""][s],
                    )[:TOP_N]
                    if fav_country
                    else []
                )
                if set(top_cc) & new_stations:
                    hits_country += 1

            curated_total = int(
                (
                    await session.execute(
                        text(
                            "SELECT COUNT(*) FROM stations "
                            "WHERE curated AND status = 'active' AND NOT hidden",
                        ),
                    )
                ).scalar_one(),
            )
            covered = {c for lst in neighbors.values() for c, _ in lst}
            curated_ids = {
                uuid.UUID(str(r[0]))
                for r in (
                    await session.execute(
                        text(
                            "SELECT id FROM stations "
                            "WHERE curated AND status = 'active' AND NOT hidden",
                        ),
                    )
                ).all()
            }
            coverage = len(covered & curated_ids) / curated_total if curated_total else 0.0

            result = {
                "event": "eval_done",
                "cutoff_days": cutoff_days,
                "identities_evaluated": evaluated,
                "recall_at_10_model": round(hits_model / evaluated, 4) if evaluated else None,
                "recall_at_10_pop_global": round(hits_global / evaluated, 4) if evaluated else None,
                "recall_at_10_pop_country": round(hits_country / evaluated, 4)
                if evaluated
                else None,
                "curated_coverage": round(coverage, 4),
            }
            log.info("eval_done", **{k: v for k, v in result.items() if k != "event"})
            typer.echo(json.dumps(result))
    finally:
        await engine.dispose()


@app.command()
def run(
    cutoff_days: int = typer.Option(default=7, help="Días de hold-out temporal."),
) -> None:
    """Evalúa recall@10 vs baselines de popularidad. Solo lectura."""
    asyncio.run(_run(cutoff_days=cutoff_days))


if __name__ == "__main__":
    app()
