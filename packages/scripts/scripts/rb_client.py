from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import httpx
from dns import resolver as dns_resolver

if TYPE_CHECKING:
    from collections.abc import Sequence


DEFAULT_TIMEOUT = 30.0
SRV_DOMAIN = "_api._tcp.radio-browser.info"


class RadioBrowserError(RuntimeError):
    pass


def _user_agent() -> str:
    ua = os.environ.get("RB_USER_AGENT", "").strip()
    if not ua:
        msg = "RB_USER_AGENT no configurado; Radio-Browser exige User-Agent identificable"
        raise RadioBrowserError(msg)
    return ua


def resolve_servers() -> list[str]:
    try:
        answers = dns_resolver.resolve(SRV_DOMAIN, "SRV")
    except Exception as exc:
        msg = f"Fallo al resolver SRV {SRV_DOMAIN}: {exc}"
        raise RadioBrowserError(msg) from exc
    hosts = [str(rdata.target).rstrip(".") for rdata in answers]
    if not hosts:
        msg = f"SRV {SRV_DOMAIN} devolvió 0 hosts"
        raise RadioBrowserError(msg)
    return hosts


class RadioBrowserClient:
    def __init__(
        self,
        *,
        servers: Sequence[str] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._servers: list[str] = list(servers) if servers else []
        self._timeout = timeout
        self._client = client or httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": _user_agent()},
            follow_redirects=True,
            max_redirects=3,
        )

    async def __aenter__(self) -> RadioBrowserClient:
        if not self._servers:
            self._servers = resolve_servers()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self._client.aclose()

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if not self._servers:
            self._servers = resolve_servers()
        last_exc: Exception | None = None
        for host in self._servers:
            url = f"https://{host}{path}"
            try:
                resp = await self._client.get(url, params=params)
                resp.raise_for_status()
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                continue
            return resp.json()
        msg = f"Todos los hosts Radio-Browser fallaron ({len(self._servers)}): {last_exc}"
        raise RadioBrowserError(msg) from last_exc

    async def fetch_stations_by_tag(self, tag: str, limit: int = 500) -> list[dict[str, Any]]:
        params = {
            "tag": tag,
            "hidebroken": "true",
            "is_https": "true",
            "limit": limit,
            "order": "clickcount",
            "reverse": "true",
        }
        data = await self.get("/json/stations/search", params=params)
        if not isinstance(data, list):
            msg = f"Respuesta inesperada de Radio-Browser para tag={tag}: no es lista"
            raise RadioBrowserError(msg)
        return [item for item in data if isinstance(item, dict)]
