"""Evidencia extra para el segundo clasificador (ADR 012): texto de la web y últimos temas.

Con solo nombre y tags el modelo deja en "unsure" más de la mitad de las emisoras dudosas. Se
le añade lo que la propia emisora dice de sí misma (``<title>``, meta-descripción, palabras clave)
y lo que está emitiendo (últimos temas guardados en ``now_playing``).

Todo es texto de terceros: se trata como dato, se acota y se limpia de espacios. La descarga
reutiliza ``fetch_html`` (tope de bytes, guard SSRF del cliente).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Any

from scripts.logo_discovery import fetch_html, is_eligible_homepage
from scripts.logo_fetch import LogoFetchError, LogoRejectedError

if TYPE_CHECKING:
    import httpx

MAX_TITLE = 140
MAX_DESCRIPTION = 320
MAX_KEYWORDS = 160
MAX_TRACKS = 8
MAX_TRACK_LENGTH = 90

_spaces = re.compile(r"\s+")


@dataclass(frozen=True)
class PageInfo:
    title: str = ""
    description: str = ""
    keywords: str = ""

    def is_empty(self) -> bool:
        return not (self.title or self.description or self.keywords)

    def as_dict(self) -> dict[str, str]:
        return {k: v for k, v in (("title", self.title), ("description", self.description),
                                  ("keywords", self.keywords)) if v}  # fmt: skip


def _clean(text: str, limit: int) -> str:
    return _spaces.sub(" ", text).strip()[:limit]


class _HeadParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta: dict[str, str] = {}
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            a = {k.lower(): (v or "") for k, v in attrs}
            name = (a.get("name") or a.get("property") or "").lower()
            if name and a.get("content") and name not in self.meta:
                self.meta[name] = a["content"]

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title and len(self.title) < 4 * MAX_TITLE:
            self.title += data


def extract_page_info(html: str) -> PageInfo:
    """``<title>``, descripción (meta o Open Graph) y palabras clave de un HTML."""
    parser = _HeadParser()
    parser.feed(html)
    parser.close()
    title = parser.title or parser.meta.get("og:title", "")
    description = parser.meta.get("description") or parser.meta.get("og:description", "")
    return PageInfo(
        title=_clean(title, MAX_TITLE),
        description=_clean(description, MAX_DESCRIPTION),
        keywords=_clean(parser.meta.get("keywords", ""), MAX_KEYWORDS),
    )


async def fetch_page_info(client: httpx.AsyncClient, homepage_url: str | None) -> PageInfo | None:
    """Información de la web de la emisora, o None si no hay web utilizable o falla la descarga.

    Cualquier error es normal (webs caídas, bloqueadas, sin HTML): se devuelve None y se sigue.
    """
    if not is_eligible_homepage(homepage_url) or homepage_url is None:
        return None
    try:
        _final_url, html = await fetch_html(client, homepage_url)
    except (LogoFetchError, LogoRejectedError):
        return None
    info = extract_page_info(html)
    return None if info.is_empty() else info


def format_tracks(now_playing: list[dict[str, Any]] | None) -> list[str]:
    """ "Artista - Título" únicos de los últimos temas, acotados (``now_playing`` de la API)."""
    out: list[str] = []
    seen: set[str] = set()
    for item in now_playing or []:
        artist = _clean(str(item.get("artist") or ""), MAX_TRACK_LENGTH)
        title = _clean(str(item.get("title") or ""), MAX_TRACK_LENGTH)
        line = f"{artist} - {title}" if artist and title else (title or artist)
        if line and line.lower() not in seen:
            seen.add(line.lower())
            out.append(line[:MAX_TRACK_LENGTH])
        if len(out) >= MAX_TRACKS:
            break
    return out
