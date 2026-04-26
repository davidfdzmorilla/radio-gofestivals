from __future__ import annotations

from typing import Callable

import httpx
import pytest

from scripts.stream_check import check_stream_alive


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        timeout=5.0,
        follow_redirects=True,
    )


# --- Alive cases ------------------------------------------------------------


async def test_200_audio_mpeg_is_alive() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "audio/mpeg"})

    async with _client(handler) as c:
        result = await check_stream_alive("http://x/stream.mp3", client=c)
    assert result.alive is True
    assert result.status_code == 200
    assert result.error is None


async def test_206_audio_aac_is_alive() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(206, headers={"content-type": "audio/aac"})

    async with _client(handler) as c:
        result = await check_stream_alive("http://x/stream.aac", client=c)
    assert result.alive is True
    assert result.status_code == 206


async def test_200_html_with_icy_name_is_alive() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html", "icy-name": "Funky Tracks"},
        )

    async with _client(handler) as c:
        result = await check_stream_alive("http://x/", client=c)
    assert result.alive is True
    assert "icy-name" in (result.error or "")


async def test_200_html_without_icy_name_is_alive_conservative() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"})

    async with _client(handler) as c:
        result = await check_stream_alive("http://x/", client=c)
    assert result.alive is True
    assert "conservative" in (result.error or "")


@pytest.mark.parametrize("status", [400, 401, 403, 405, 410, 418])
async def test_4xx_non_404_is_alive(status: int) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(status)

    async with _client(handler) as c:
        result = await check_stream_alive("http://x/", client=c)
    assert result.alive is True, f"status {status} wrongly marked dead"
    assert result.status_code == status


async def test_redirect_to_audio_follows() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/redirect":
            return httpx.Response(301, headers={"location": "http://x/final.mp3"})
        return httpx.Response(200, headers={"content-type": "audio/mpeg"})

    async with _client(handler) as c:
        result = await check_stream_alive("http://x/redirect", client=c)
    assert result.alive is True
    assert result.status_code == 200


# --- Dead cases -------------------------------------------------------------


async def test_404_is_dead() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    async with _client(handler) as c:
        result = await check_stream_alive("http://x/", client=c)
    assert result.alive is False
    assert result.status_code == 404


@pytest.mark.parametrize("status", [500, 502, 503, 504])
async def test_5xx_is_dead(status: int) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(status)

    async with _client(handler) as c:
        result = await check_stream_alive("http://x/", client=c)
    assert result.alive is False
    assert result.status_code == status


async def test_connect_error_is_dead() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    async with _client(handler) as c:
        result = await check_stream_alive("http://x/", client=c)
    assert result.alive is False
    assert "connect error" in (result.error or "")


async def test_unexpected_status_3xx_unhandled_is_dead() -> None:
    # 3xx that doesn't redirect (e.g. raw 304 with no Location)
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(304)

    async with _client(handler) as c:
        result = await check_stream_alive("http://x/", client=c)
    # 304 with no body falls through to "unhandled status"
    assert result.alive is False
    assert result.status_code == 304


# --- Result shape -----------------------------------------------------------


async def test_result_includes_latency_and_content_type() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "audio/mpeg"})

    async with _client(handler) as c:
        result = await check_stream_alive("http://x/stream.mp3", client=c)
    assert result.latency_ms >= 0
    assert result.content_type == "audio/mpeg"
