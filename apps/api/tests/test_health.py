from __future__ import annotations

from httpx import AsyncClient


async def test_root_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}
