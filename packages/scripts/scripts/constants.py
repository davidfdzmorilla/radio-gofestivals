from __future__ import annotations

from typing import Final

ELECTRONIC_TAGS: Final[list[str]] = [
    "techno",
    "house",
    "deep house",
    "tech house",
    "minimal",
    "trance",
    "progressive",
    "drum and bass",
    "dnb",
    "dubstep",
    "ambient",
    "hardstyle",
    "breakbeat",
    "electronic",
    "edm",
]

# Mapeo tag sucio → genre slug canónico.
# Claves ya normalizadas (lower + strip + espacios colapsados).
TAG_ALIASES: Final[dict[str, str]] = {
    "drum and bass": "dnb",
    "drum-and-bass": "dnb",
    "drum'n'bass": "dnb",
    "drumandbass": "dnb",
    "d&b": "dnb",
    "dn&b": "dnb",
    "dnb": "dnb",
    "deephouse": "deep-house",
    "deep house": "deep-house",
    "deep-house": "deep-house",
    "techhouse": "tech-house",
    "tech house": "tech-house",
    "tech-house": "tech-house",
    "minimal techno": "minimal",
    "minimal-techno": "minimal",
    "progressive trance": "progressive",
    "progressive-house": "progressive",
    "liquid dnb": "liquid-dnb",
    "liquid drum and bass": "liquid-dnb",
    "edm": "electronic",
    "electronica": "electronic",
    "electro": "electronic",
}
