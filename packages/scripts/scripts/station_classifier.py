"""Clasificador de reglas "¿es una emisora de música electrónica?" (Fase 1, modo sombra).

Función pura: a partir de los tags crudos de Radio-Browser y el nombre devuelve una
puntuación 0-100 y un estado. No toca la base de datos ni decide nada por sí sola: en esta
fase solo se registra el veredicto para medirlo contra el catálogo real.

Criterio de frontera (decisión de David, 2026-11-06): cuenta todo género electrónico de nuestra
taxonomía. Ambient, chill-out, downtempo y lounge son electrónica y puntúan como tags claros; lo
que queda como señal *suave* es lo genérico (dance, club, dj, mix), que también usa el pop. Los
tags ambiguos (progressive, minimal…) solo suman junto a un tag electrónico claro, porque solos
son tan probables de rock progresivo o de música minimalista.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from scripts.taxonomy_mapper import normalize_tag

ACCEPT_AT: Final = 70
REJECT_AT: Final = 30

# Sin ningún tag electrónico claro (solo dance/club/dj…) la emisora nunca se acepta sola.
SOFT_ONLY_CAP: Final = ACCEPT_AT - 1
BASE_SCORE: Final = 50
STRONG_WEIGHT: Final = 25
STRONG_CAP: Final = 3
SOFT_WEIGHT: Final = 10
SOFT_CAP: Final = 2
AMBIGUOUS_WEIGHT: Final = 5
NEGATIVE_WEIGHT: Final = 20
NEGATIVE_CAP: Final = 3
NAME_WEIGHT: Final = 10
MAX_TAGS: Final = 30
MAX_TAG_LENGTH: Final = 64

# Electrónica inequívoca.
STRONG_TAGS: Final[frozenset[str]] = frozenset(
    {
        "techno", "house", "deep house", "tech house", "progressive house", "electro house",
        "acid house", "trance", "psytrance", "psy trance", "goa trance", "progressive trance",
        "edm", "electro", "electronica", "electronic", "electronic music", "electronic dance music",
        "dnb", "drum and bass", "drum n bass", "drum'n'bass", "drumandbass", "jungle", "liquid dnb",
        "dubstep", "hardstyle", "hard techno", "hardtechno", "schranz", "breakbeat", "breaks",
        "idm", "synthwave", "rave", "eurodance", "uk garage", "minimal techno", "tekno", "makina",
        "gabber", "happy hardcore", "future bass", "electroclash", "trip hop",
        "nu disco", "italo disco", "italo dance", "italodance", "eurobeat", "darkwave", "ebm",
        "minimal wave", "dark electro", "dark techno", "bass house", "future garage", "chillstep",
        "ambient", "dark ambient", "chillout", "chill out", "chill-out", "downtempo", "lounge",
        "nu-disco", "afro house", "industrial", "uk-garage", "experimental electronic",
        "psybient", "vaporwave", "chiptune", "glitch", "breakcore", "eletronic", "eletronica",
        "electronico",
    }
)  # fmt: skip
# Cercanas a la electrónica pero no concluyentes por sí solas.
SOFT_TAGS: Final[frozenset[str]] = frozenset(
    {
        "chill", "dance", "club", "dj", "mix", "beats", "synth",
    }
)  # fmt: skip
# Significan otra cosa si van solos (prog rock, hardcore punk, música minimalista…).
AMBIGUOUS_TAGS: Final[frozenset[str]] = frozenset(
    {"progressive", "minimal", "hardcore", "garage", "bass", "deep"}
)
# Un género que indica que NO es una radio de electrónica.
NEGATIVE_TAGS: Final[frozenset[str]] = frozenset(
    {
        "rock", "metal", "heavy metal", "punk", "indie", "alternative", "folk", "country",
        "jazz", "blues", "classical", "classic rock", "gospel", "christian", "religious",
        "news", "talk", "sports", "politics", "oldies", "schlager", "latin", "reggae",
        "top 40", "pop", "hits", "public radio", "kids", "comedy", "soul", "funk", "r&b",
        "hip hop", "rap", "world", "podcast", "variety", "adult contemporary", "80s", "90s",
        "documentary", "history", "culture", "education", "educational", "technology",
        "meditation", "yoga", "healing", "relaxation", "video game music", "soundtracks", "spa",
    }
)  # fmt: skip

_NAME_STRONG = re.compile(
    r"\b(techno|house|trance|d(?:rum)?[ &'n]*b(?:ass)?|dnb|dubstep|electro(?:nic)?|edm|rave|"
    r"hardstyle|psy|minimal|club|beats|dj)\b",
    re.IGNORECASE,
)
_NAME_NEGATIVE = re.compile(
    r"\b(rock|metal|jazz|talk|news|noticias|gospel|christian|country|reggae|oldies|classic|"
    r"folk|blues|sport|sports|schlager|katolik|catholic|cristian[oa]?)\b",
    re.IGNORECASE,
)

_token_split = re.compile(r"[^\w']+", re.UNICODE)


@dataclass(frozen=True)
class Classification:
    score: int
    state: str  # accepted | review | rejected
    reason: str


def normalize_tags(raw_tags: list[str]) -> list[str]:
    """Tags normalizados, sin duplicados y acotados (se guardan en la base de datos)."""
    seen: dict[str, None] = {}
    for raw in raw_tags:
        tag = normalize_tag(raw)[:MAX_TAG_LENGTH]
        if tag:
            seen.setdefault(tag, None)
        if len(seen) >= MAX_TAGS:
            break
    return list(seen)


def _hits(tags: list[str], vocabulary: frozenset[str]) -> list[str]:
    """Tags que coinciden entero con el vocabulario, o con todas sus palabras en orden.

    "deep house" coincide con "deep house" y "melodic techno" con "techno", pero "housewives"
    no coincide con "house": se compara por palabras, no por subcadena.
    """
    found: dict[str, None] = {}
    for tag in tags:
        if tag in vocabulary:
            found.setdefault(tag, None)
            continue
        words = [w for w in _token_split.split(tag) if w]
        for term in vocabulary:
            term_words = term.split()
            n = len(term_words)
            if n > len(words):
                continue
            if any(words[i : i + n] == term_words for i in range(len(words) - n + 1)):
                found.setdefault(term, None)
    return list(found)


def state_for(score: int) -> str:
    if score >= ACCEPT_AT:
        return "accepted"
    if score <= REJECT_AT:
        return "rejected"
    return "review"


def classify(rb_tags: list[str], name: str) -> Classification:
    tags = normalize_tags(rb_tags)
    strong = _hits(tags, STRONG_TAGS)
    soft = [t for t in _hits(tags, SOFT_TAGS) if t not in strong]
    ambiguous = _hits(tags, AMBIGUOUS_TAGS)
    negative = _hits(tags, NEGATIVE_TAGS)

    score = BASE_SCORE
    score += STRONG_WEIGHT * min(len(strong), STRONG_CAP)
    score += SOFT_WEIGHT * min(len(soft), SOFT_CAP)
    if strong:
        score += AMBIGUOUS_WEIGHT * min(len(ambiguous), 2)
    score -= NEGATIVE_WEIGHT * min(len(negative), NEGATIVE_CAP)

    name_pos = bool(_NAME_STRONG.search(name))
    name_neg = bool(_NAME_NEGATIVE.search(name))
    if name_pos and not name_neg:
        score += NAME_WEIGHT
    elif name_neg and not name_pos:
        score -= NAME_WEIGHT

    if not strong:
        score = min(score, SOFT_ONLY_CAP)
    score = max(0, min(100, score))
    parts: list[str] = []
    if strong:
        parts.append("strong:" + ",".join(strong[:5]))
    if soft:
        parts.append("soft:" + ",".join(soft[:5]))
    if negative:
        parts.append("neg:" + ",".join(negative[:5]))
    if name_pos and not name_neg:
        parts.append("name+")
    elif name_neg and not name_pos:
        parts.append("name-")
    if not tags:
        parts.append("no-tags")
    return Classification(
        score=score, state=state_for(score), reason=" ".join(parts) or "no-signal"
    )
