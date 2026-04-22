from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from scripts.constants import TAG_ALIASES

MIN_TAG_LENGTH = 3
FUZZY_THRESHOLD = 0.85
FUZZY_CONFIDENCE_FACTOR = 80
ALIAS_CONFIDENCE = 90
EXACT_CONFIDENCE = 100

_digits_only = re.compile(r"^\d+$")
_non_word = re.compile(r"^[^\w]+$", re.UNICODE)
_multi_space = re.compile(r"\s+")


@dataclass(frozen=True)
class GenreRef:
    id: int
    slug: str


def normalize_tag(tag: str) -> str:
    decomposed = unicodedata.normalize("NFKD", tag)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _multi_space.sub(" ", stripped.strip().lower())


def _is_noise(tag: str) -> bool:
    if len(tag) < MIN_TAG_LENGTH:
        return True
    if _digits_only.match(tag):
        return True
    return bool(_non_word.match(tag))


def _best_fuzzy(tag: str, slugs: list[str]) -> tuple[str, float] | None:
    best: tuple[str, float] | None = None
    for slug in slugs:
        ratio = SequenceMatcher(None, tag, slug).ratio()
        if ratio > FUZZY_THRESHOLD and (best is None or ratio > best[1]):
            best = (slug, ratio)
    return best


def map_rb_tags_to_genre_slugs(
    rb_tags: list[str],
    existing_genres: list[GenreRef],
) -> list[tuple[int, int]]:
    by_slug: dict[str, int] = {g.slug: g.id for g in existing_genres}
    slugs = list(by_slug.keys())

    best_by_gid: dict[int, int] = {}

    for raw in rb_tags:
        normalized = normalize_tag(raw)
        if _is_noise(normalized):
            continue

        if normalized in by_slug:
            gid = by_slug[normalized]
            best_by_gid[gid] = max(best_by_gid.get(gid, 0), EXACT_CONFIDENCE)
            continue

        alias = TAG_ALIASES.get(normalized)
        if alias and alias in by_slug:
            gid = by_slug[alias]
            best_by_gid[gid] = max(best_by_gid.get(gid, 0), ALIAS_CONFIDENCE)
            continue

        fuzzy = _best_fuzzy(normalized, slugs)
        if fuzzy is not None:
            slug, ratio = fuzzy
            confidence = int(ratio * FUZZY_CONFIDENCE_FACTOR)
            gid = by_slug[slug]
            best_by_gid[gid] = max(best_by_gid.get(gid, 0), confidence)

    return list(best_by_gid.items())
