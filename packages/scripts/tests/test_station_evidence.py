from __future__ import annotations

import httpx
import respx

from scripts.station_evidence import (
    MAX_DESCRIPTION,
    MAX_TITLE,
    MAX_TRACKS,
    PageInfo,
    extract_page_info,
    fetch_page_info,
    format_tracks,
)

HTML = """<html><head>
<title>  Anti Radio
 | Techno &amp; House  </title>
<meta name="description" content="La mejor   música electrónica 24/7">
<meta name="keywords" content="techno, house, trance">
<meta property="og:description" content="OG desc">
</head><body><h1>x</h1></body></html>"""


def test_extracts_title_description_and_keywords_cleaned() -> None:
    info = extract_page_info(HTML)
    assert info.title == "Anti Radio | Techno & House"
    assert info.description == "La mejor música electrónica 24/7"
    assert info.keywords == "techno, house, trance"


def test_falls_back_to_open_graph() -> None:
    info = extract_page_info(
        '<title></title><meta property="og:title" content="OG T">'
        '<meta property="og:description" content="OG D">',
    )
    assert (info.title, info.description) == ("OG T", "OG D")


def test_everything_is_bounded() -> None:
    html = f'<title>{"t" * 1000}</title><meta name="description" content="{"d" * 5000}">'
    info = extract_page_info(html)
    assert len(info.title) == MAX_TITLE
    assert len(info.description) == MAX_DESCRIPTION


def test_empty_page_info() -> None:
    assert extract_page_info("<html><body>hola</body></html>").is_empty()
    assert PageInfo().as_dict() == {}
    assert PageInfo(title="a").as_dict() == {"title": "a"}


@respx.mock
async def test_fetch_page_info_reads_the_homepage() -> None:
    respx.get("https://radio.example/").respond(200, html=HTML)
    async with httpx.AsyncClient() as client:
        info = await fetch_page_info(client, "https://radio.example/")
    assert info is not None
    assert info.keywords == "techno, house, trance"


@respx.mock
async def test_fetch_page_info_returns_none_on_errors_and_missing_urls() -> None:
    respx.get("https://down.example/").respond(500)
    respx.get("https://pdf.example/").respond(
        200, headers={"content-type": "application/pdf"}, content=b"x"
    )
    respx.get("https://empty.example/").respond(200, html="<html><body>sin nada</body></html>")
    async with httpx.AsyncClient() as client:
        assert await fetch_page_info(client, "https://down.example/") is None
        assert await fetch_page_info(client, "https://pdf.example/") is None
        assert await fetch_page_info(client, "https://empty.example/") is None
        assert await fetch_page_info(client, None) is None
        assert await fetch_page_info(client, "") is None
        # plataformas genéricas: su <title> es el de la plataforma, no el de la emisora
        assert await fetch_page_info(client, "https://www.facebook.com/radio") is None


def test_format_tracks_dedupes_bounds_and_handles_missing_parts() -> None:
    items = [
        {"artist": "Simply Red", "title": "Close To You"},
        {"artist": "simply red", "title": "close to you"},
        {"artist": "", "title": "Solo título"},
        {"artist": "Solo artista", "title": None},
        {"artist": None, "title": None},
        *[{"artist": f"A{i}", "title": f"T{i}"} for i in range(20)],
    ]
    out = format_tracks(items)
    assert out[:3] == ["Simply Red - Close To You", "Solo título", "Solo artista"]
    assert len(out) == MAX_TRACKS
    assert format_tracks(None) == []
