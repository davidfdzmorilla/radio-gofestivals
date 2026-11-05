"""Descubrimiento del icono de marca de una emisora a partir de su web (ADR 011, addendum).

Si el favicon de Radio-Browser no sirve (no existe, 404, demasiado pequeño), `fetch-logos`
lee la web de la emisora UNA vez y busca su icono: `apple-touch-icon` (suele ser un logo
cuadrado de 120-180 px) y `<link rel=icon>`. Medido sobre 120 webs reales, esas dos
fuentes dan logos de calidad; `og:image` no (son fotos y banners), así que no se usa.

Se descartan las webs de redes sociales, plataformas y constructores genéricos: su icono
es el de la plataforma (el logo de Wix o de Facebook), no el de la emisora.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import TYPE_CHECKING
from urllib.parse import urldefrag, urljoin, urlsplit

import httpx

from scripts.logo_fetch import HTTP_OK, USER_AGENT, LogoFetchError, LogoRejectedError
from scripts.url_guard import BlockedAddressError

if TYPE_CHECKING:
    from collections.abc import Iterable

MAX_HTML_BYTES = 300_000
MAX_CANDIDATES = 6
MAX_URL_LENGTH = 2048
# Un `sizes` declarado por debajo de esto no sirve para una portada: ni se descarga.
MIN_DECLARED_SIDE = 64
CONVENTION_PATH = "/apple-touch-icon.png"

# Webs cuyo icono es el de la plataforma, no el de la emisora. Se comparan por dominio
# (el propio o un subdominio), nunca por subcadena: `xlukradio.com` no es `radio.co`.
DENIED_DOMAINS = frozenset(
    {
        # redes sociales y perfiles
        "facebook.com",
        "fb.com",
        "fb.me",
        "instagram.com",
        "twitter.com",
        "x.com",
        "youtube.com",
        "youtu.be",
        "tiktok.com",
        "linktr.ee",
        "soundcloud.com",
        "mixcloud.com",
        "bandcamp.com",
        "patreon.com",
        "twitch.tv",
        "discord.com",
        "discord.gg",
        "t.me",
        "telegram.me",
        "vk.com",
        "ok.ru",
        "myspace.com",
        "linkedin.com",
        "pinterest.com",
        "reddit.com",
        "spotify.com",
        "deezer.com",
        "whatsapp.com",
        "threads.net",
        # directorios y plataformas de radio
        "laut.fm",
        "zeno.fm",
        "tunein.com",
        "radio.net",
        "radio.garden",
        "onlineradiobox.com",
        "streema.com",
        "mytuner-radio.com",
        "live365.com",
        "radionomy.com",
        "radioking.com",
        "shoutcast.com",
        "caster.fm",
        # constructores de sitios y alojamientos genéricos
        "wixsite.com",
        "wix.com",
        "editorx.io",
        "blogspot.com",
        "wordpress.com",
        "weebly.com",
        "webnode.com",
        "jimdofree.com",
        "jimdosite.com",
        "sites.google.com",
        "google.com",
        "github.io",
        "netlify.app",
        "vercel.app",
        "herokuapp.com",
        "carrd.co",
        "squarespace.com",
        "godaddysites.com",
        "strikingly.com",
        "yolasite.com",
        "webflow.io",
        "notion.site",
        "ucoz.com",
        "ucoz.net",
        "ucoz.ru",
    },
)


def is_eligible_homepage(url: str | None) -> bool:
    """True si `url` es una web propia de la emisora de la que merece la pena leer el icono."""
    if not url:
        return False
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower().removeprefix("www.")
    if parts.scheme not in {"http", "https"} or not host:
        return False
    return not any(host == d or host.endswith(f".{d}") for d in DENIED_DOMAINS)


@dataclass(frozen=True)
class IconCandidate:
    kind: str  # "apple-touch-icon" | "link-icon" | "convention"
    url: str
    size: int  # lado declarado en `sizes`; 0 = no declarado


_SIZE_RE = re.compile(r"(\d+)\s*x\s*\d+", re.IGNORECASE)
_UNKNOWN_FIRST_PRIORITY = {"apple-touch-icon": 0, "link-icon": 1, "convention": 2}


class _IconParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.raw: list[tuple[str, str, int]] = []  # (kind, href, size)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "link":
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        href = a.get("href", "").strip()
        if not href or href.lower().startswith(("data:", "javascript:")):
            return
        # `rel` es un conjunto de palabras: "mask-icon" (Safari, SVG) no cuenta como "icon".
        rel = set(a.get("rel", "").lower().split())
        if "svg" in a.get("type", "").lower() or urlsplit(href).path.lower().endswith(".svg"):
            return  # SVG es XML, no raster: nunca se descarga
        sizes = [int(n) for n in _SIZE_RE.findall(a.get("sizes", ""))]
        size = max(sizes, default=0)
        if any(t.startswith("apple-touch-icon") for t in rel):
            self.raw.append(("apple-touch-icon", href, size))
        elif "icon" in rel:
            self.raw.append(("link-icon", href, size))


def extract_icon_candidates(html: str, page_url: str) -> list[IconCandidate]:
    """Candidatos de icono de `html`, del mejor al peor, resueltos contra `page_url`."""
    parser = _IconParser()
    parser.feed(html[:MAX_HTML_BYTES])
    parser.close()

    out: list[IconCandidate] = []
    seen: set[str] = set()

    def add(kind: str, href: str, size: int) -> None:
        url = urldefrag(urljoin(page_url, href))[0]
        if len(url) > MAX_URL_LENGTH or urlsplit(url).scheme not in {"http", "https"}:
            return
        if url in seen:
            return
        seen.add(url)
        out.append(IconCandidate(kind=kind, url=url, size=size))

    usable = [r for r in parser.raw if r[2] == 0 or r[2] >= MIN_DECLARED_SIDE]
    # apple-touch-icon antes que link-icon; dentro de cada uno, los de mayor lado declarado
    # primero y los sin declarar al final de su grupo.
    usable.sort(key=lambda r: (_UNKNOWN_FIRST_PRIORITY[r[0]], r[2] == 0, -r[2]))
    for kind, href, size in usable:
        add(kind, href, size)
    parts = urlsplit(page_url)
    add("convention", f"{parts.scheme}://{parts.netloc}{CONVENTION_PATH}", 0)
    return out[:MAX_CANDIDATES]


async def fetch_html(client: httpx.AsyncClient, url: str) -> tuple[str, str]:
    """(URL final, HTML) de `url`, con tope de bytes. El cliente debe llevar el guard SSRF."""
    try:
        async with client.stream(
            "GET",
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml;q=0.9"},
        ) as response:
            if response.status_code != HTTP_OK:
                msg = f"homepage http {response.status_code}"
                raise LogoFetchError(msg)
            ctype = response.headers.get("content-type", "").lower()
            if "html" not in ctype:
                msg = "homepage is not html"
                raise LogoFetchError(msg)
            buf = bytearray()
            async for chunk in response.aiter_bytes():
                buf.extend(chunk)
                if len(buf) >= MAX_HTML_BYTES:
                    break  # el <head> está al principio: no hace falta más
            html = bytes(buf[:MAX_HTML_BYTES]).decode(response.encoding or "utf-8", "replace")
            return str(response.url), html
    except BlockedAddressError as exc:
        msg = f"blocked: {exc}"
        raise LogoRejectedError(msg) from exc
    except httpx.HTTPError as exc:
        msg = f"homepage {type(exc).__name__}: {str(exc)[:100]}"
        raise LogoFetchError(msg) from exc


def describe(candidates: Iterable[IconCandidate]) -> str:
    return ", ".join(f"{c.kind}:{c.url}" for c in candidates)
