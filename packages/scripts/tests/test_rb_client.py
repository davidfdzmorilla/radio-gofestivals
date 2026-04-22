from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest
import respx

from scripts import rb_client as rb_client_mod
from scripts.rb_client import RadioBrowserClient, RadioBrowserError, resolve_servers

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


class _FakeSRV:
    def __init__(self, target: str) -> None:
        self.target = target


def test_srv_resolution(mocker: MockerFixture) -> None:
    mocker.patch(
        "scripts.rb_client.dns_resolver.resolve",
        return_value=[_FakeSRV("de1.api.radio-browser.info."), _FakeSRV("nl1.api.radio-browser.info.")],
    )
    hosts = resolve_servers()
    assert hosts == ["de1.api.radio-browser.info", "nl1.api.radio-browser.info"]


def test_srv_resolution_empty_raises(mocker: MockerFixture) -> None:
    mocker.patch("scripts.rb_client.dns_resolver.resolve", return_value=[])
    with pytest.raises(RadioBrowserError):
        resolve_servers()


@respx.mock
async def test_fetch_with_retry_on_timeout() -> None:
    respx.get("https://host-a.example/json/stations/search").mock(
        side_effect=httpx.TimeoutException("boom"),
    )
    respx.get("https://host-b.example/json/stations/search").respond(
        json=[{"stationuuid": "u1", "name": "S"}],
    )
    async with RadioBrowserClient(servers=["host-a.example", "host-b.example"]) as cli:
        data = await cli.fetch_stations_by_tag("techno")
    assert data == [{"stationuuid": "u1", "name": "S"}]


@respx.mock
async def test_all_hosts_fail_raises() -> None:
    respx.get("https://host-a.example/json/stations/search").respond(status_code=500)
    respx.get("https://host-b.example/json/stations/search").respond(status_code=502)
    async with RadioBrowserClient(servers=["host-a.example", "host-b.example"]) as cli:
        with pytest.raises(RadioBrowserError):
            await cli.fetch_stations_by_tag("techno")


@respx.mock
async def test_user_agent_header_set() -> None:
    route = respx.get("https://host-a.example/json/stations/search").respond(json=[])
    async with RadioBrowserClient(servers=["host-a.example"]) as cli:
        await cli.fetch_stations_by_tag("techno")
    assert route.called
    assert "User-Agent" in route.calls.last.request.headers
    assert "radio.gofestivals" in route.calls.last.request.headers["User-Agent"]


@respx.mock
async def test_hidebroken_forced_true() -> None:
    route = respx.get("https://host-a.example/json/stations/search").respond(json=[])
    async with RadioBrowserClient(servers=["host-a.example"]) as cli:
        await cli.fetch_stations_by_tag("techno")
    assert route.called
    assert route.calls.last.request.url.params.get("hidebroken") == "true"
    assert route.calls.last.request.url.params.get("tag") == "techno"


def test_ua_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RB_USER_AGENT", raising=False)
    with pytest.raises(RadioBrowserError):
        rb_client_mod._user_agent()  # noqa: SLF001
