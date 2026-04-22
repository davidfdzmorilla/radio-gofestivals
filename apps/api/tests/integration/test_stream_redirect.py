from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import AsyncClient


async def test_302_redirect_to_stream_url(client: AsyncClient, create_station) -> None:  # type: ignore[no-untyped-def]
    await create_station(slug="vivo-stream", stream_url="https://stream.example.com/live.mp3")

    r = await client.get("/api/v1/stations/vivo-stream/stream", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "https://stream.example.com/live.mp3"


async def test_stream_404_for_missing(client: AsyncClient) -> None:
    r = await client.get("/api/v1/stations/no-such/stream", follow_redirects=False)
    assert r.status_code == 404


async def test_rate_limit_triggers_429(client: AsyncClient, create_station) -> None:  # type: ignore[no-untyped-def]
    await create_station(slug="rl-test", stream_url="https://s.example.com/x.mp3")

    ok_responses = 0
    rate_limited = False
    for _ in range(75):
        r = await client.get("/api/v1/stations/rl-test/stream", follow_redirects=False)
        if r.status_code == 302:
            ok_responses += 1
        elif r.status_code == 429:
            rate_limited = True
            break

    assert ok_responses <= 60
    assert rate_limited is True
