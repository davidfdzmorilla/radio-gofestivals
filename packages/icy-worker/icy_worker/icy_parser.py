from __future__ import annotations

import re
from typing import TypedDict

_TITLE_PATTERN = re.compile(r"StreamTitle=(?P<quote>['\"]?)(?P<val>.*?)(?P=quote)\s*(?:;|$)")


class ParsedMetadata(TypedDict):
    title: str | None
    artist: str | None
    raw: str


def parse_icy_metadata(raw: bytes) -> ParsedMetadata:
    """Parse un bloque ICY metadata (ya sin byte de length).

    Reglas:
    - Decodifica latin-1 (no falla nunca) y quita padding `\\x00`.
    - Extrae `StreamTitle=...` (con o sin comillas) hasta `;` o EOL.
    - Si el valor contiene ' - ', divide en artist y title.
    - Si no hay split, artist=None y title=valor completo.
    - Si falta StreamTitle o está vacío → title/artist=None, raw=''.
    """
    text = raw.decode("latin-1").rstrip("\x00").strip()
    if not text:
        return {"title": None, "artist": None, "raw": ""}

    match = _TITLE_PATTERN.search(text)
    if not match:
        return {"title": None, "artist": None, "raw": ""}

    stream_title = match.group("val")
    if not stream_title:
        return {"title": None, "artist": None, "raw": ""}

    # "Artist - Title": primer separador " - " divide
    if " - " in stream_title:
        artist_part, _, title_part = stream_title.partition(" - ")
        return {
            "title": title_part.strip() or None,
            "artist": artist_part.strip() or None,
            "raw": stream_title,
        }

    return {"title": stream_title.strip() or None, "artist": None, "raw": stream_title}
