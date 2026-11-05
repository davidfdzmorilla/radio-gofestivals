"""Descarga y procesado seguro de logos de emisoras (ADR 011).

El `favicon` de Radio-Browser apunta a un host de un tercero. Aquí se descarga con
límites estrictos, se decodifica, se valida y se RE-CODIFICA a WebP: lo que servimos
es siempre nuestra copia, nunca los bytes de origen (un SVG o un GIF con trampa no
llegan nunca a un navegador). Capas: guard SSRF en cada petición y redirección
(`url_guard`), tope de bytes durante la descarga, dimensiones comprobadas ANTES de
decodificar (bombas de descompresión) y solo formatos raster conocidos.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO
from typing import TYPE_CHECKING

import httpx
from PIL import Image, ImageChops, ImageOps, UnidentifiedImageError

from scripts.url_guard import BlockedAddressError

if TYPE_CHECKING:
    from collections.abc import Mapping

MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024
# Un favicon de 5000x5000 son 25 MP: ya es absurdo. Se comprueba con la cabecera de la
# imagen, antes de decodificar nada.
MAX_PIXELS = 25_000_000
MIN_SIDE = 64
SIZES: Mapping[str, int] = {"sm": 112, "lg": 256}
WEBP_QUALITY = 82
# Formatos raster que Pillow decodifica de forma segura. SVG no está (es XML, no raster).
ALLOWED_FORMATS = frozenset({"PNG", "JPEG", "WEBP", "GIF", "ICO", "BMP"})
HASH_LENGTH = 12
# El logo se muestra sobre un recuadro claro (--fg-0 de la web). Uno casi blanco o casi
# transparente se perdería: se rechaza si menos de un 2 % de sus píxeles se distingue.
TILE_RGB = (250, 250, 249)
VISIBLE_DIFF = 24
MIN_VISIBLE_FRACTION = 0.02
HTTP_OK = 200
USER_AGENT = "radio.gofestivals/1.0 (+https://radio.gofestivals.eu; logo fetcher)"


class LogoRejectedError(Exception):
    """La imagen no sirve y no mejorará por reintentar (no es raster, es minúscula…)."""


class LogoFetchError(Exception):
    """Fallo al descargar (red, HTTP, tamaño): puede arreglarse solo; se reintenta con backoff."""


@dataclass(frozen=True)
class ProcessedLogo:
    content_hash: str
    sm: bytes
    lg: bytes
    width: int
    height: int


def _encode(img: Image.Image, side: int) -> bytes:
    resized = ImageOps.contain(img, (side, side), method=Image.Resampling.LANCZOS)
    out = BytesIO()
    resized.save(out, format="WEBP", quality=WEBP_QUALITY, method=4)
    return out.getvalue()


def _visible_on_light(rgba: Image.Image) -> bool:
    background = Image.new("RGBA", rgba.size, (*TILE_RGB, 255))
    flat = Image.alpha_composite(background, rgba).convert("RGB")
    diff = ImageChops.difference(flat, Image.new("RGB", flat.size, TILE_RGB)).convert("L")
    visible = sum(diff.histogram()[VISIBLE_DIFF + 1 :])
    return visible / (rgba.width * rgba.height) >= MIN_VISIBLE_FRACTION


def process_image(data: bytes) -> ProcessedLogo:
    """Valida `data` y devuelve dos copias WebP propias. Lanza `LogoRejectedError` si no sirve."""
    try:
        img = Image.open(BytesIO(data))
        fmt = img.format
        width, height = img.size  # solo cabecera: aún no se ha decodificado la imagen
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        msg = "not a decodable raster image"
        raise LogoRejectedError(msg) from exc
    if fmt not in ALLOWED_FORMATS:
        msg = f"format not allowed: {fmt}"
        raise LogoRejectedError(msg)
    if width * height > MAX_PIXELS:
        msg = f"too many pixels: {width}x{height}"
        raise LogoRejectedError(msg)
    if min(width, height) < MIN_SIDE:
        msg = f"too small: {width}x{height}"
        raise LogoRejectedError(msg)
    try:
        img.seek(0)  # GIF animado: primer fotograma
        rgba = ImageOps.exif_transpose(img).convert("RGBA")
        if not _visible_on_light(rgba):
            msg = "invisible on a light background"
            raise LogoRejectedError(msg)
        sm = _encode(rgba, SIZES["sm"])
        lg = _encode(rgba, SIZES["lg"])
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        msg = "image failed to decode"
        raise LogoRejectedError(msg) from exc
    digest = hashlib.sha256(lg).hexdigest()[:HASH_LENGTH]
    return ProcessedLogo(content_hash=digest, sm=sm, lg=lg, width=width, height=height)


async def download(client: httpx.AsyncClient, url: str) -> bytes:
    """Descarga `url` con tope de bytes. El cliente debe llevar el guard SSRF (`guard_request`)."""
    try:
        async with client.stream(
            "GET",
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "image/*,*/*;q=0.5"},
        ) as response:
            if response.status_code != HTTP_OK:
                msg = f"http {response.status_code}"
                raise LogoFetchError(msg)
            declared = response.headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > MAX_DOWNLOAD_BYTES:
                msg = f"too large (declared {declared} bytes)"
                raise LogoRejectedError(msg)
            ctype = response.headers.get("content-type", "").lower()
            if ctype.startswith(("text/", "application/json", "application/xml")):
                msg = f"not an image (content-type {ctype.split(';')[0]})"
                raise LogoFetchError(msg)
            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    msg = f"too large (> {MAX_DOWNLOAD_BYTES} bytes)"
                    raise LogoRejectedError(msg)
                chunks.append(chunk)
            return b"".join(chunks)
    except BlockedAddressError as exc:
        # La URL (o una redirección) apunta a una dirección interna: no se reintenta.
        msg = f"blocked: {exc}"
        raise LogoRejectedError(msg) from exc
    except httpx.HTTPError as exc:
        msg = f"{type(exc).__name__}: {str(exc)[:120]}"
        raise LogoFetchError(msg) from exc


async def fetch_logo(client: httpx.AsyncClient, url: str) -> ProcessedLogo:
    """Descarga y procesa un logo. `LogoFetchError` = reintentar; `LogoRejectedError` = no."""
    return process_image(await download(client, url))
