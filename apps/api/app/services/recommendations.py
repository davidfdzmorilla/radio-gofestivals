"""Recomendaciones de emisoras (docs/recommendations-plan.md §3-§4, ADR 004).

Blend lineal on-the-fly sobre la similitud precomputada en
station_similarity, con re-rank de diversidad (apply_genre_cap por género
primario + cap por país) y dos slots de exploración. Cold start por
país/idioma del locale del navegador. Cache Redis por identidad.
"""

from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING

from app.repos import recommendations as recs_repo
from app.repos.stations import (
    apply_genre_cap,
    get_active_station_by_slug,
    list_featured_diverse_stations,
)
from app.schemas.station import StationsPage, StationSummary
from app.services.stations import _to_summary

if TYPE_CHECKING:
    import uuid

    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.repos.recommendations import CandidateMeta

# Pesos del blend (§3.2). Ajustar solo tras comparar offline (§7).
W_SIMILARITY = 0.30
W_QUALITY = 0.20
W_GENRE_AFFINITY = 0.15
W_LANGUAGE = 0.10
W_TREND = 0.10
W_LOCAL_POP = 0.10
W_COUNTRY = 0.05

SEED_DECAY_DAYS = 30.0
SEED_FAVORITE_BONUS = 3.0
SEED_VOTE_BONUS = 1.0
MAX_SEEDS = 10
KNOWN_PLAYS_THRESHOLD = 3  # >=3 plays: ya la conoce, no recomendarla
GENRE_CAP = 3
COUNTRY_CAP = 6
EXPLORATION_SLOTS = (4, 9)  # índices 0-based: slots 5 y 10

REC_CACHE_TTL = 600
COLD_CACHE_TTL = 1800
SIMILAR_CACHE_TTL = 3600

# stations.language usa nombres en minúscula de Radio-Browser.
_LOCALE_LANGUAGES = {
    "es": "spanish",
    "en": "english",
    "de": "german",
    "fr": "french",
    "it": "italian",
    "pt": "portuguese",
    "nl": "dutch",
    "pl": "polish",
    "ru": "russian",
}


def parse_locale(locale: str | None) -> tuple[str | None, str | None]:
    """'es-ES' -> (país 'ES', idioma 'spanish'). Tolerante con basura."""
    if not locale:
        return None, None
    parts = locale.replace("_", "-").split("-")
    lang = _LOCALE_LANGUAGES.get(parts[0].lower()) if parts[0] else None
    country = None
    if len(parts) > 1 and len(parts[1]) == 2 and parts[1].isalpha():  # noqa: PLR2004
        country = parts[1].upper()
    return country, lang


def _seed_weights(
    plays: list[tuple[uuid.UUID, int, float]],
    favorites: set[uuid.UUID],
    votes: set[uuid.UUID],
) -> dict[uuid.UUID, float]:
    weights: dict[uuid.UUID, float] = {}
    for sid, n_plays, days_ago in plays:
        weights[sid] = n_plays * math.exp(-days_ago / SEED_DECAY_DAYS)
    for sid in favorites:
        weights[sid] = weights.get(sid, 0.0) + SEED_FAVORITE_BONUS
    for sid in votes:
        weights[sid] = weights.get(sid, 0.0) + SEED_VOTE_BONUS
    return weights


def _cosine(a: dict[int, float], b: dict[int, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(w * b[g] for g, w in a.items() if g in b)
    if dot == 0.0:
        return 0.0
    return dot / (
        math.sqrt(sum(w * w for w in a.values())) * math.sqrt(sum(w * w for w in b.values()))
    )


def _blend_scores(
    candidates: dict[uuid.UUID, float],
    meta: dict[uuid.UUID, CandidateMeta],
    genre_affinity: dict[uuid.UUID, float],
    *,
    user_language: str | None,
    user_country: str | None,
    max_plays_30d: int,
) -> list[tuple[float, uuid.UUID]]:
    scored: list[tuple[float, uuid.UUID]] = []
    log_max_pop = math.log1p(max_plays_30d) if max_plays_30d > 0 else 1.0
    for cid, sim_component in candidates.items():
        m = meta.get(cid)
        if m is None:  # inactiva/oculta: fuera
            continue
        trend = m["click_trend"]
        trend_norm = max(0.0, min(1.0, (max(-1.0, min(1.0, trend)) + 1.0) / 2.0))
        pop_norm = math.log1p(m["plays_30d"]) / log_max_pop
        score = (
            W_SIMILARITY * sim_component
            + W_QUALITY * m["quality"] / 100.0
            + W_GENRE_AFFINITY * genre_affinity.get(cid, 0.0)
            + W_LANGUAGE * (1.0 if user_language and m["language"] == user_language else 0.0)
            + W_TREND * trend_norm
            + W_LOCAL_POP * pop_norm
            + W_COUNTRY * (1.0 if user_country and m["country"] == user_country else 0.0)
        )
        scored.append((score, cid))
    scored.sort(key=lambda t: (-t[0], t[1].bytes))
    return scored


def _apply_country_cap(
    ordered_ids: list[uuid.UUID],
    meta: dict[uuid.UUID, CandidateMeta],
    *,
    size: int,
) -> list[uuid.UUID]:
    """Máximo COUNTRY_CAP por país; sin país => sin cap (bucket único)."""
    buckets: dict[str, int] = {}
    items: list[tuple[uuid.UUID, int | None]] = []
    synthetic = 10_000  # buckets únicos para emisoras sin país
    for sid in ordered_ids:
        m = meta.get(sid)
        country = m["country"] if m else None
        if country is None:
            synthetic += 1
            items.append((sid, synthetic))
        else:
            items.append((sid, buckets.setdefault(str(country), len(buckets))))
    return apply_genre_cap(items, size=size, cap=COUNTRY_CAP)


async def _hydrate_page(
    session: AsyncSession,
    ordered_ids: list[uuid.UUID],
) -> StationsPage:
    by_id = await recs_repo.get_stations_by_ids(session, ordered_ids)
    summaries: list[StationSummary] = [
        _to_summary(by_id[sid]) for sid in ordered_ids if sid in by_id
    ]
    return StationsPage(
        items=summaries,
        total=len(summaries),
        page=1,
        size=len(summaries),
        pages=1 if summaries else 0,
    )


async def _cold_start_ids(
    session: AsyncSession,
    *,
    country: str | None,
    language: str | None,
    size: int,
) -> list[uuid.UUID]:
    """País/idioma del visitante por quality; relleno con featured global."""
    ids = await recs_repo.get_cold_start_ids(
        session,
        country=country,
        language=language,
        limit=size,
    )
    if len(ids) < size:
        featured = await list_featured_diverse_stations(
            session,
            size=size,
            genre_cap=GENRE_CAP,
        )
        seen = set(ids)
        ids.extend(s.id for s in featured if s.id not in seen)
    return ids[:size]


async def get_recommendations(
    session: AsyncSession,
    redis: Redis[str],
    *,
    user_id: uuid.UUID | None,
    client_id: uuid.UUID | None,
    locale: str | None,
    size: int,
) -> StationsPage:
    country, language = parse_locale(locale)
    if user_id is not None:
        cache_key = f"rec:v1:user:{user_id}:{size}"
    elif client_id is not None:
        cache_key = f"rec:v1:client:{client_id}:{size}"
    else:
        cache_key = f"rec:v1:cold:{country}:{language}:{size}"

    cached = await redis.get(cache_key)
    if cached is not None:
        return StationsPage.model_validate(json.loads(cached))

    page = await _compute_recommendations(
        session,
        user_id=user_id,
        client_id=client_id,
        country=country,
        language=language,
        size=size,
    )
    ttl = REC_CACHE_TTL if (user_id or client_id) else COLD_CACHE_TTL
    await redis.set(cache_key, page.model_dump_json(), ex=ttl)
    return page


async def _compute_recommendations(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    client_id: uuid.UUID | None,
    country: str | None,
    language: str | None,
    size: int,
) -> StationsPage:
    plays = await recs_repo.get_seed_plays(
        session,
        user_id=user_id,
        client_id=client_id,
    )
    favorites: set[uuid.UUID] = set()
    votes: set[uuid.UUID] = set()
    if user_id is not None:
        favorites, votes = await recs_repo.get_user_marked_stations(session, user_id)

    weights = _seed_weights(plays, favorites, votes)
    if not weights:
        ids = await _cold_start_ids(
            session,
            country=country,
            language=language,
            size=size,
        )
        return await _hydrate_page(session, ids)

    top_seeds = [
        sid for sid, _ in sorted(weights.items(), key=lambda t: (-t[1], t[0].bytes))[:MAX_SEEDS]
    ]
    max_weight = max(weights[s] for s in top_seeds)

    # Candidatas: vecinas de las semillas, excluyendo conocidas y favoritas.
    known = {sid for sid, n, _ in plays if n >= KNOWN_PLAYS_THRESHOLD} | favorites
    neighbors = await recs_repo.get_neighbors(session, top_seeds)
    candidates: dict[uuid.UUID, float] = {}
    for seed_id, cand_id, sim in neighbors:
        if cand_id in known:
            continue
        contribution = (weights[seed_id] / max_weight) * sim
        candidates[cand_id] = max(candidates.get(cand_id, 0.0), contribution)

    if not candidates:
        ids = await _cold_start_ids(
            session,
            country=country,
            language=language,
            size=size,
        )
        return await _hydrate_page(session, ids)

    candidate_ids = list(candidates)
    meta = await recs_repo.get_candidate_meta(session, candidate_ids)
    vectors = await recs_repo.get_genre_weights(session, top_seeds + candidate_ids)

    profile: dict[int, float] = {}
    for sid in top_seeds:
        norm = weights[sid] / max_weight
        for gid, w in vectors.get(sid, {}).items():
            profile[gid] = profile.get(gid, 0.0) + norm * w
    genre_affinity = {cid: _cosine(profile, vectors.get(cid, {})) for cid in candidate_ids}

    max_pop = max((int(m["plays_30d"]) for m in meta.values()), default=0)
    scored = _blend_scores(
        candidates,
        meta,
        genre_affinity,
        user_language=language,
        user_country=country,
        max_plays_30d=max_pop,
    )
    ordered = [cid for _, cid in scored]

    # Diversidad: cap por género primario y por país.
    primary = await recs_repo.get_primary_genres(session, ordered)
    capped = apply_genre_cap(
        [(sid, primary.get(sid)) for sid in ordered],
        size=size * 2,  # margen para la segunda pasada
        cap=GENRE_CAP,
    )
    final_ids = _apply_country_cap(capped, meta, size=size)

    # Exploración: emisoras frescas compatibles en los slots fijos.
    profile_genres = sorted(profile, key=lambda g: -profile[g])[:5]
    picks = await recs_repo.get_exploration_picks(
        session,
        genre_ids=profile_genres,
        exclude=final_ids + list(known) + top_seeds,
        limit=len(EXPLORATION_SLOTS),
    )
    for slot, pick in zip(EXPLORATION_SLOTS, picks, strict=False):
        if slot < len(final_ids):
            final_ids[slot] = pick
        else:
            final_ids.append(pick)

    return await _hydrate_page(session, final_ids[:size])


async def get_similar_stations(
    session: AsyncSession,
    redis: Redis[str],
    *,
    slug: str,
    size: int,
) -> list[StationSummary] | None:
    """Vecinas públicas de una emisora. None si el slug no existe."""
    cache_key = f"sim:v1:{slug}:{size}"
    cached = await redis.get(cache_key)
    if cached is not None:
        return [StationSummary.model_validate(s) for s in json.loads(cached)]

    station = await get_active_station_by_slug(session, slug)
    if station is None:
        return None
    ids = await recs_repo.get_similar_ids(session, station.id, limit=size)
    by_id = await recs_repo.get_stations_by_ids(session, ids)
    summaries = [_to_summary(by_id[i]) for i in ids if i in by_id]
    await redis.set(
        cache_key,
        json.dumps([s.model_dump(mode="json") for s in summaries]),
        ex=SIMILAR_CACHE_TTL,
    )
    return summaries
