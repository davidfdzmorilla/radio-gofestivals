"""Descubrimiento del icono de marca desde la web de la emisora (ADR 011, addendum)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest

from scripts import url_guard
from scripts.logo_discovery import (
    DENIED_DOMAINS,
    MAX_CANDIDATES,
    MAX_HTML_BYTES,
    extract_icon_candidates,
    fetch_html,
    is_eligible_homepage,
)
from scripts.logo_fetch import USER_AGENT, LogoFetchError, LogoRejectedError
from scripts.url_guard import guard_request

if TYPE_CHECKING:
    from collections.abc import Callable

PAGE = "https://radio.example/index.html"


def _urls(html: str, page: str = PAGE) -> list[str]:
    return [c.url for c in extract_icon_candidates(html, page)]


# --- webs elegibles ----------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://technolovers.fm/",
        "https://radiorecord.ru/radio/",
        "http://www.somafm.com",
        "https://xlukradio.com",  # contiene "radio.co" y NO es radio.co
        "https://notfacebook.com",
        "https://facebook.com.evil.example/x",
        "https://radio.example.co.uk/live",
    ],
)
def test_own_websites_are_eligible(url: str) -> None:
    assert is_eligible_homepage(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://facebook.com/miradio",
        "https://www.facebook.com/miradio",
        "https://m.facebook.com/miradio",
        "https://es-es.facebook.com/miradio",
        "https://instagram.com/miradio",
        "https://x.com/miradio",
        "https://youtu.be/abc",
        "https://linktr.ee/miradio",
        "https://usuario.wixsite.com/radio",
        "https://miradio.blogspot.com",
        "https://miradio.wordpress.com",
        "https://laut.fm/miradio",
        "https://zeno.fm/miradio",
        "https://tunein.com/radio/x",
        "https://radio.net/s/x",
        "https://sites.google.com/view/radio",
        "https://usuario.github.io/radio",
        "HTTPS://WWW.FACEBOOK.COM/X",
    ],
)
def test_social_networks_platforms_and_site_builders_are_not(url: str) -> None:
    assert not is_eligible_homepage(url)


@pytest.mark.parametrize(
    "url",
    [
        None,
        "",
        "   ",
        "ftp://radio.example",
        "javascript:alert(1)",
        "//radio.example",
        "radio.example",
    ],
)
def test_non_http_or_empty_urls_are_not_eligible(url: str | None) -> None:
    assert not is_eligible_homepage(url)


def test_the_denylist_has_no_overly_broad_entries() -> None:
    # Se compara por dominio completo: una entrada sin punto matchearía demasiado.
    assert all("." in d for d in DENIED_DOMAINS)


# --- extracción de candidatos --------------------------------------------------


def test_apple_touch_icon_comes_before_link_icon_and_larger_sizes_first() -> None:
    html = """<head>
      <link rel="icon" href="/fav-128.png" sizes="128x128">
      <link rel="apple-touch-icon" href="/ati-120.png" sizes="120x120">
      <link rel="apple-touch-icon" href="/ati-180.png" sizes="180x180">
      <link rel="icon" href="/fav-256.png" sizes="256x256">
    </head>"""
    assert _urls(html)[:4] == [
        "https://radio.example/ati-180.png",
        "https://radio.example/ati-120.png",
        "https://radio.example/fav-256.png",
        "https://radio.example/fav-128.png",
    ]


def test_icons_without_a_declared_size_go_last_in_their_group() -> None:
    html = '<link rel="apple-touch-icon" href="/a.png"><link rel="apple-touch-icon" href="/b.png" sizes="152x152">'
    assert _urls(html)[:2] == ["https://radio.example/b.png", "https://radio.example/a.png"]


@pytest.mark.parametrize(
    "rel",
    [
        "icon",
        "shortcut icon",
        "SHORTCUT ICON",
        "apple-touch-icon",
        "apple-touch-icon-precomposed",
        "alternate icon",
    ],
)
def test_recognizes_the_usual_rel_values(rel: str) -> None:
    assert "https://radio.example/i.png" in _urls(f'<link rel="{rel}" href="/i.png">')


@pytest.mark.parametrize(
    "link",
    [
        '<link rel="mask-icon" href="/m.svg">',
        '<link rel="icon" href="/i.svg">',
        '<link rel="icon" type="image/svg+xml" href="/i.png">',
        '<link rel="icon" href="/I.SVG?v=2">',
        '<link rel="icon" href="data:image/png;base64,AAAA">',
        '<link rel="icon" href="javascript:alert(1)">',
        '<link rel="icon" href="">',
        '<link rel="stylesheet" href="/x.css">',
        '<link rel="preload" href="/f.png" as="image">',
        '<meta property="og:image" content="/og.jpg">',
        '<meta name="twitter:image" content="/tw.jpg">',
    ],
)
def test_ignores_svg_data_uris_and_everything_that_is_not_a_brand_icon(link: str) -> None:
    urls = _urls(link)
    assert urls == ["https://radio.example/apple-touch-icon.png"]  # solo la convención


def test_og_image_is_deliberately_not_used() -> None:
    # Medido sobre webs reales: son fotos y banners, no logos.
    assert all(
        "og" not in u
        for u in _urls('<meta property="og:image" content="https://radio.example/og.jpg">')
    )


@pytest.mark.parametrize(
    ("href", "expected"),
    [
        ("/a.png", "https://radio.example/a.png"),
        ("a.png", "https://radio.example/dir/a.png"),
        ("../a.png", "https://radio.example/a.png"),
        ("//cdn.example/a.png", "https://cdn.example/a.png"),
        ("https://cdn.example/a.png#frag", "https://cdn.example/a.png"),
        ("http://cdn.example/a.png", "http://cdn.example/a.png"),
    ],
)
def test_urls_are_resolved_against_the_page(href: str, expected: str) -> None:
    assert (
        extract_icon_candidates(
            f'<link rel="icon" href="{href}">', "https://radio.example/dir/page.html"
        )[0].url
        == expected
    )


def test_relative_urls_use_the_final_page_url_not_a_base_tag() -> None:
    html = '<base href="https://evil.example/"><link rel="icon" href="a.png">'
    assert _urls(html)[0] == "https://radio.example/a.png"


def test_declared_sizes_that_are_too_small_are_not_even_downloaded() -> None:
    html = '<link rel="icon" href="/16.png" sizes="16x16"><link rel="icon" href="/32.ico" sizes="32x32"><link rel="icon" href="/64.png" sizes="64x64">'
    assert _urls(html)[0] == "https://radio.example/64.png"
    assert "https://radio.example/16.png" not in _urls(html)
    assert "https://radio.example/32.ico" not in _urls(html)


def test_the_apple_touch_icon_convention_is_always_a_last_resort() -> None:
    assert _urls("<html></html>") == ["https://radio.example/apple-touch-icon.png"]
    own = _urls('<link rel="apple-touch-icon" href="/apple-touch-icon.png">')
    assert own == ["https://radio.example/apple-touch-icon.png"]  # sin duplicar
    assert (
        _urls("<html></html>", "http://radio.example:8080/x")[0]
        == "http://radio.example:8080/apple-touch-icon.png"
    )


def test_candidates_are_capped_and_deduplicated() -> None:
    html = "".join(
        f'<link rel="icon" href="/i{n}.png" sizes="{100 + n}x{100 + n}">' for n in range(20)
    )
    html += '<link rel="icon" href="/i3.png">'
    urls = _urls(html)
    assert len(urls) == MAX_CANDIDATES
    assert len(set(urls)) == len(urls)


def test_a_data_or_non_http_resolved_url_is_dropped() -> None:
    assert _urls('<link rel="icon" href="ftp://x.example/a.png">') == [
        "https://radio.example/apple-touch-icon.png"
    ]


def test_overlong_urls_are_dropped() -> None:
    assert _urls(f'<link rel="icon" href="/{"a" * 3000}.png">') == [
        "https://radio.example/apple-touch-icon.png"
    ]


@pytest.mark.parametrize(
    "html",
    [
        "",
        "<",
        "<link",
        '<link rel="icon" href="/a.png"',
        "<<<>>><link/><link rel>",
        "\x00\x01<link rel=icon href=/a.png>",
        "<html><head><title>x",
    ],
)
def test_broken_html_never_raises(html: str) -> None:
    extract_icon_candidates(html, PAGE)


def test_tags_after_the_size_cap_are_ignored() -> None:
    html = "x" * (MAX_HTML_BYTES + 10) + '<link rel="icon" href="/late.png">'
    assert "https://radio.example/late.png" not in _urls(html)


# --- fetch_html ----------------------------------------------------------------


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
        event_hooks={"request": [guard_request]},
    )


def _html(
    status: int = 200, body: bytes = b"<html></html>", ctype: str = "text/html; charset=utf-8"
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(_r: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=body, headers={"content-type": ctype})

    return handler


@pytest.fixture(autouse=True)
def _public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALLOW_PRIVATE_STREAM_HOSTS", raising=False)

    async def fake(_host: str, _port: int) -> list[str]:
        return ["93.184.216.34"]

    monkeypatch.setattr(url_guard, "_resolve", fake)


async def test_fetch_html_returns_the_final_url_and_the_markup() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.host == "old.example":
            return httpx.Response(301, headers={"location": "https://new.example/home"})
        assert req.headers["user-agent"] == USER_AGENT
        assert "referer" not in req.headers
        return httpx.Response(
            200, content=b"<html>ok</html>", headers={"content-type": "text/html"}
        )

    async with _client(handler) as c:
        final, html = await fetch_html(c, "http://old.example/")
    assert final == "https://new.example/home"
    assert html == "<html>ok</html>"


@pytest.mark.parametrize("status", [403, 404, 410, 429, 500, 503])
async def test_http_errors_are_retryable_failures(status: int) -> None:
    async with _client(_html(status)) as c:
        with pytest.raises(LogoFetchError, match=str(status)):
            await fetch_html(c, "https://radio.example/")


@pytest.mark.parametrize(
    "ctype", ["application/json", "image/png", "application/pdf", "text/plain"]
)
async def test_a_page_that_is_not_html_is_a_failure(ctype: str) -> None:
    async with _client(_html(ctype=ctype)) as c:
        with pytest.raises(LogoFetchError, match="not html"):
            await fetch_html(c, "https://radio.example/")


async def test_the_page_is_cut_at_the_size_cap_without_failing() -> None:
    body = b"<html><head>" + b"x" * (MAX_HTML_BYTES * 3)
    async with _client(_html(body=body)) as c:
        _, html = await fetch_html(c, "https://radio.example/")
    assert len(html) <= MAX_HTML_BYTES


class _EndlessBody(httpx.AsyncByteStream):
    """Cuerpo de 10 MB en trozos de 10 KB; cuenta cuánto se llegó a leer."""

    CHUNK = 10_000

    def __init__(self) -> None:
        self.sent = 0

    async def __aiter__(self):  # type: ignore[no-untyped-def]
        for _ in range(1000):
            self.sent += self.CHUNK
            yield b"x" * self.CHUNK


async def test_a_huge_page_stops_being_read_at_the_cap() -> None:
    body = _EndlessBody()

    def handler(_r: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=body, headers={"content-type": "text/html"})

    async with _client(handler) as c:
        await fetch_html(c, "https://radio.example/")
    assert body.sent <= MAX_HTML_BYTES + _EndlessBody.CHUNK  # no se descargan los 10 MB


async def test_a_network_error_is_retryable() -> None:
    def boom(_r: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow")

    async with _client(boom) as c:
        with pytest.raises(LogoFetchError, match="ConnectTimeout"):
            await fetch_html(c, "https://radio.example/")


@pytest.mark.parametrize(
    "url", ["http://127.0.0.1:6379/", "http://169.254.169.254/", "http://[::1]/"]
)
async def test_internal_homepages_are_rejected_without_connecting(url: str) -> None:
    calls = 0

    def handler(_r: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200)

    async with _client(handler) as c:
        with pytest.raises(LogoRejectedError, match="blocked"):
            await fetch_html(c, url)
    assert calls == 0


async def test_a_homepage_that_redirects_to_an_internal_address_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake(host: str, _port: int) -> list[str]:
        return ["10.0.0.9"] if host == "internal.example" else ["93.184.216.34"]

    monkeypatch.setattr(url_guard, "_resolve", fake)
    seen: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.url.host)
        return httpx.Response(302, headers={"location": "http://internal.example/x"})

    async with _client(handler) as c:
        with pytest.raises(LogoRejectedError, match="blocked"):
            await fetch_html(c, "https://radio.example/")
    assert seen == ["radio.example"]
