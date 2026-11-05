"""Procesado y descarga de logos (ADR 011): lo que sirve es siempre una copia propia."""

from __future__ import annotations

import socket
from io import BytesIO
from typing import TYPE_CHECKING

import httpx
import pytest
from PIL import Image

from scripts import url_guard
from scripts.logo_fetch import (
    MAX_DOWNLOAD_BYTES,
    MIN_SIDE,
    SIZES,
    LogoFetchError,
    LogoRejectedError,
    download,
    fetch_logo,
    process_image,
)
from scripts.url_guard import guard_request

if TYPE_CHECKING:
    from collections.abc import Callable


def _image(fmt: str, size: tuple[int, int] = (200, 120), mode: str = "RGBA") -> bytes:
    color = (30, 140, 220, 255) if mode == "RGBA" else (30, 140, 220)
    out = BytesIO()
    Image.new(mode, size, color).save(out, format=fmt)
    return out.getvalue()


def _decode(data: bytes) -> Image.Image:
    img = Image.open(BytesIO(data))
    img.load()
    return img


# --- process_image ----------------------------------------------------------


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP", "GIF", "BMP"])
def test_decodes_common_raster_formats_into_two_webp_copies(fmt: str) -> None:
    mode = "RGB" if fmt in {"JPEG", "BMP"} else "RGBA"
    logo = process_image(_image(fmt, mode=mode))

    for data, side in ((logo.sm, SIZES["sm"]), (logo.lg, SIZES["lg"])):
        img = _decode(data)
        assert img.format == "WEBP"  # nunca los bytes de origen
        assert max(img.size) <= side
    assert len(logo.content_hash) == 12
    assert logo.width == 200
    assert logo.height == 120


def test_keeps_aspect_ratio_and_never_upscales_beyond_the_target() -> None:
    logo = process_image(_image("PNG", (1000, 400)))
    w, h = _decode(logo.lg).size
    assert w == SIZES["lg"]
    assert abs(w / h - 2.5) < 0.05
    assert max(_decode(logo.sm).size) == SIZES["sm"]


def test_preserves_transparency() -> None:
    out = BytesIO()
    canvas = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    canvas.paste(Image.new("RGBA", (80, 80), (200, 30, 60, 255)), (24, 24))  # logo con forma
    canvas.save(out, format="PNG")
    corner = _decode(process_image(out.getvalue()).lg).convert("RGBA").getpixel((2, 2))
    assert corner is not None
    assert corner[3] == 0  # fuera del logo sigue siendo transparente


def test_ico_uses_the_largest_size_and_accepts_it() -> None:
    out = BytesIO()
    Image.new("RGBA", (128, 128), (200, 50, 50, 255)).save(
        out, format="ICO", sizes=[(16, 16), (128, 128)]
    )
    assert process_image(out.getvalue()).width == 128


def test_animated_gif_uses_the_first_frame() -> None:
    frames = [Image.new("RGBA", (100, 100), c) for c in ((255, 0, 0, 255), (0, 255, 0, 255))]
    out = BytesIO()
    frames[0].save(out, format="GIF", save_all=True, append_images=frames[1:], loop=0)
    logo = process_image(out.getvalue())
    r, g, _b, _a = _decode(logo.lg).convert("RGBA").getpixel((50, 50))
    assert r > g  # el primer fotograma, rojo


def test_same_content_same_hash_and_different_content_different_hash() -> None:
    a = process_image(_image("PNG"))
    assert a.content_hash == process_image(_image("PNG")).content_hash
    out = BytesIO()
    Image.new("RGBA", (200, 120), (220, 30, 30, 255)).save(out, format="PNG")
    assert a.content_hash != process_image(out.getvalue()).content_hash


@pytest.mark.parametrize(
    ("data", "why"),
    [
        (
            b"<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><script>alert(1)</script></svg>",
            "svg",
        ),
        (b"<html><body>404 not found</body></html>", "html"),
        (b"", "empty"),
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * 20, "truncated png"),
        (b"GIF89a" + b"\x00" * 10, "truncated gif"),
        (b"not an image at all", "garbage"),
    ],
)
def test_rejects_anything_that_is_not_a_decodable_raster(data: bytes, why: str) -> None:
    with pytest.raises(LogoRejectedError):
        process_image(data)


@pytest.mark.parametrize("fmt", ["TIFF", "PPM", "PCX", "TGA"])
def test_rejects_decodable_formats_that_are_not_on_the_allow_list(fmt: str) -> None:
    # Pillow SÍ sabe decodificarlos, pero un favicon web no es de esos: se descartan.
    data = _image(fmt, (128, 128), mode="RGB")
    assert Image.open(BytesIO(data)).format == fmt  # el test es válido: Pillow lo reconoce
    with pytest.raises(LogoRejectedError, match="format not allowed"):
        process_image(data)


def test_rejects_images_that_are_too_small_to_look_good() -> None:
    side = MIN_SIDE - 1
    with pytest.raises(LogoRejectedError, match="too small"):
        process_image(_image("PNG", (side, 200)))
    process_image(_image("PNG", (MIN_SIDE, MIN_SIDE)))  # el límite exacto sí vale


def test_rejects_a_pixel_bomb_from_the_header_without_decoding_it() -> None:
    # 6000x6000 = 36 MP de un solo color: el PNG pesa pocos KB pero decodificarlo cuesta GB.
    out = BytesIO()
    Image.new("L", (6000, 6000), 128).save(out, format="PNG", optimize=True)
    assert len(out.getvalue()) < MAX_DOWNLOAD_BYTES
    with pytest.raises(LogoRejectedError, match="too many pixels"):
        process_image(out.getvalue())


# --- download / fetch_logo ---------------------------------------------------


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
        max_redirects=3,
        event_hooks={"request": [guard_request]},
    )


def _respond(status: int = 200, **kwargs: object) -> Callable[[httpx.Request], httpx.Response]:
    """Handler de MockTransport que responde siempre lo mismo."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, **kwargs)  # type: ignore[arg-type]

    return handler


def _dns(monkeypatch: pytest.MonkeyPatch, table: dict[str, list[str]]) -> None:
    async def fake(host: str, _port: int) -> list[str]:
        if host not in table:
            raise socket.gaierror("nxdomain")
        return table[host]

    monkeypatch.setattr(url_guard, "_resolve", fake)


@pytest.fixture(autouse=True)
def _guard_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALLOW_PRIVATE_STREAM_HOSTS", raising=False)


async def test_fetch_logo_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    _dns(monkeypatch, {"cdn.example": ["93.184.216.34"]})
    png = _image("PNG")
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, content=png, headers={"content-type": "image/png"})

    async with _client(handler) as c:
        logo = await fetch_logo(c, "https://cdn.example/logo.png")
    assert _decode(logo.lg).format == "WEBP"
    assert "radio.gofestivals" in seen[0].headers["user-agent"]
    assert "referer" not in seen[0].headers  # no se filtra de dónde venimos


@pytest.mark.parametrize("status", [404, 403, 410, 429, 500, 503])
async def test_http_errors_are_retryable_failures(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    _dns(monkeypatch, {"cdn.example": ["93.184.216.34"]})
    async with _client(_respond(status)) as c:
        with pytest.raises(LogoFetchError, match=str(status)):
            await download(c, "https://cdn.example/logo.png")


async def test_html_error_pages_are_failures_not_images(monkeypatch: pytest.MonkeyPatch) -> None:
    # Protección anti-hotlink típica: 200 con una página HTML.
    _dns(monkeypatch, {"cdn.example": ["93.184.216.34"]})
    handler = _respond(200, content=b"<html>blocked</html>", headers={"content-type": "text/html"})
    async with _client(handler) as c:
        with pytest.raises(LogoFetchError, match="not an image"):
            await download(c, "https://cdn.example/logo.png")


async def test_network_errors_are_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    _dns(monkeypatch, {"cdn.example": ["93.184.216.34"]})

    def boom(_r: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow")

    async with _client(boom) as c:
        with pytest.raises(LogoFetchError, match="ConnectTimeout"):
            await download(c, "https://cdn.example/logo.png")


async def test_oversized_download_is_cut_off_mid_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    _dns(monkeypatch, {"cdn.example": ["93.184.216.34"]})
    big = b"\x00" * (MAX_DOWNLOAD_BYTES + 1024)
    # Sin Content-Length declarado: hay que cortar mientras se descarga.
    stream = httpx.ByteStream(big)
    handler = _respond(200, stream=stream, headers={"content-type": "image/png"})
    async with _client(handler) as c:
        with pytest.raises(LogoRejectedError, match="too large"):
            await download(c, "https://cdn.example/logo.png")


async def test_declared_oversize_is_rejected_before_reading_the_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dns(monkeypatch, {"cdn.example": ["93.184.216.34"]})
    handler = _respond(
        200,
        content=b"x",
        headers={"content-type": "image/png", "content-length": str(MAX_DOWNLOAD_BYTES + 1)},
    )
    async with _client(handler) as c:
        with pytest.raises(LogoRejectedError, match="too large"):
            await download(c, "https://cdn.example/logo.png")


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:6379/logo.png",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/x.png",
    ],
)
async def test_internal_urls_are_rejected_without_connecting(url: str) -> None:
    calls = 0

    def handler(_r: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200)

    async with _client(handler) as c:
        with pytest.raises(LogoRejectedError, match="blocked"):
            await download(c, url)
    assert calls == 0


async def test_a_redirect_to_an_internal_address_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dns(monkeypatch, {"cdn.example": ["93.184.216.34"], "internal.example": ["10.0.0.7"]})
    seen: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.url.host)
        return httpx.Response(302, headers={"location": "http://internal.example/secret.png"})

    async with _client(handler) as c:
        with pytest.raises(LogoRejectedError, match="blocked"):
            await download(c, "https://cdn.example/logo.png")
    assert seen == ["cdn.example"]


async def test_garbage_bytes_served_as_an_image_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dns(monkeypatch, {"cdn.example": ["93.184.216.34"]})
    handler = _respond(
        200, content=b"<svg onload=alert(1)>", headers={"content-type": "image/svg+xml"}
    )
    async with _client(handler) as c:
        with pytest.raises(LogoRejectedError):
            await fetch_logo(c, "https://cdn.example/logo.svg")


# --- visibilidad sobre el recuadro claro --------------------------------------


def _png(canvas: Image.Image) -> bytes:
    out = BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()


def _on_transparent(shape_color: tuple[int, int, int, int], shape: int, side: int = 128) -> bytes:
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    offset = (side - shape) // 2
    canvas.paste(Image.new("RGBA", (shape, shape), shape_color), (offset, offset))
    return _png(canvas)


@pytest.mark.parametrize(
    ("data", "why"),
    [
        (_png(Image.new("RGBA", (128, 128), (0, 0, 0, 0))), "totalmente transparente"),
        (_on_transparent((255, 255, 255, 255), 100), "logo blanco sobre transparente"),
        (_on_transparent((248, 248, 247, 255), 100), "logo casi blanco"),
        (_png(Image.new("RGB", (128, 128), (255, 255, 255))), "fondo blanco liso"),
        (_png(Image.new("RGB", (128, 128), (252, 251, 250))), "casi del color del recuadro"),
        (_on_transparent((20, 20, 20, 255), 8), "un punto de menos del 2 % del área"),
    ],
)
def test_a_logo_that_would_vanish_on_the_light_tile_is_rejected(data: bytes, why: str) -> None:
    with pytest.raises(LogoRejectedError, match="invisible"):
        process_image(data)


@pytest.mark.parametrize(
    "data",
    [
        _on_transparent((20, 20, 20, 255), 100),
        _on_transparent((200, 30, 60, 255), 100),
        _on_transparent((30, 140, 220, 255), 40),
        _png(Image.new("RGB", (128, 128), (10, 10, 10))),
        _png(Image.new("RGB", (128, 128), (0, 180, 90))),
    ],
)
def test_dark_and_colored_logos_are_accepted(data: bytes) -> None:
    process_image(data)


def test_a_white_logo_on_a_dark_background_is_accepted() -> None:
    canvas = Image.new("RGBA", (128, 128), (15, 15, 15, 255))
    canvas.paste(Image.new("RGBA", (60, 60), (255, 255, 255, 255)), (34, 34))
    process_image(_png(canvas))  # el fondo oscuro es parte del logo: se ve sobre el recuadro


def test_a_semi_transparent_dark_logo_is_still_visible() -> None:
    process_image(_on_transparent((0, 0, 0, 140), 100))
