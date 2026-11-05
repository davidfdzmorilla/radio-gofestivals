"""Guard SSRF: ninguna petición saliente puede ir a una dirección no pública (ADR 008)."""

from __future__ import annotations

import ipaddress
import socket

import httpx
import pytest

from scripts import url_guard
from scripts.stream_check import check_stream_alive
from scripts.url_guard import BlockedAddressError, assert_public_url, guard_request, is_public_ip

PRIVATE = [
    "127.0.0.1",
    "10.0.0.5",
    "172.16.0.1",
    "192.168.1.1",
    "169.254.169.254",
    "100.64.0.1",
    "0.0.0.0",  # noqa: S104
    "224.0.0.1",
    "::1",
    "fc00::1",
    "fe80::1",
    "::ffff:10.0.0.1",
    "::ffff:127.0.0.1",
]
# Si alguien edita la lista y pierde casos por error, esto lo detecta.
assert len(PRIVATE) == 13, "PRIVATE debe tener 13 direcciones"
PUBLIC = ["8.8.8.8", "1.1.1.1", "93.184.216.34", "2606:4700:4700::1111"]


@pytest.fixture(autouse=True)
def _guard_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALLOW_PRIVATE_STREAM_HOSTS", raising=False)


def _dns(monkeypatch: pytest.MonkeyPatch, table: dict[str, list[str]]) -> None:
    async def fake(host: str, _port: int) -> list[str]:
        if host not in table:
            raise socket.gaierror("nxdomain")
        return table[host]

    monkeypatch.setattr(url_guard, "_resolve", fake)


@pytest.mark.parametrize("ip", PRIVATE)
def test_non_public_ips_are_rejected(ip: str) -> None:
    assert not is_public_ip(ipaddress.ip_address(ip))


@pytest.mark.parametrize("ip", PUBLIC)
def test_public_ips_are_accepted(ip: str) -> None:
    assert is_public_ip(ipaddress.ip_address(ip))


@pytest.mark.parametrize(
    "host", ["127.0.0.1", "10.0.0.5", "169.254.169.254", "[::1]", "[fe80::1]", "[::ffff:10.0.0.1]"]
)
async def test_literal_private_hosts_are_blocked(host: str) -> None:
    with pytest.raises(BlockedAddressError):
        await assert_public_url(f"http://{host}:6379/")


async def test_literal_public_host_is_allowed() -> None:
    await assert_public_url("http://8.8.8.8:8000/stream")
    await assert_public_url("https://[2606:4700:4700::1111]/stream")


async def test_hostname_resolving_to_private_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    _dns(monkeypatch, {"evil.example": ["10.0.0.9"]})
    with pytest.raises(BlockedAddressError, match=r"10\.0\.0\.9"):
        await assert_public_url("http://evil.example/stream")


async def test_hostname_with_one_private_record_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    _dns(monkeypatch, {"mixed.example": ["93.184.216.34", "127.0.0.1"]})
    with pytest.raises(BlockedAddressError):
        await assert_public_url("http://mixed.example/stream")


async def test_hostname_resolving_to_public_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    _dns(monkeypatch, {"radio.example": ["93.184.216.34", "2606:4700:4700::1111"]})
    await assert_public_url("https://radio.example/stream")


async def test_unresolvable_hostname_is_left_to_the_real_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _dns(monkeypatch, {})
    await assert_public_url("http://no-such-host.example/stream")  # no lanza


async def test_escape_hatch_for_local_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOW_PRIVATE_STREAM_HOSTS", "true")
    await assert_public_url("http://127.0.0.1:8000/stream")


def test_blocked_error_is_a_normal_httpx_error() -> None:
    # Los handlers existentes (`except httpx.HTTPError`) lo tratan como fallo de red.
    assert issubclass(BlockedAddressError, httpx.RequestError)
    assert issubclass(BlockedAddressError, httpx.HTTPError)


async def test_every_redirect_hop_is_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    # Una URL pública que redirige a una interna: el caso típico de SSRF.
    _dns(monkeypatch, {"cdn.example": ["93.184.216.34"], "internal.example": ["10.0.0.1"]})
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        return httpx.Response(302, headers={"location": "http://internal.example/secret"})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
        event_hooks={"request": [guard_request]},
    )
    async with client:
        with pytest.raises(BlockedAddressError):
            await client.get("http://cdn.example/stream")
    assert seen == ["cdn.example"]  # el segundo salto no llegó a salir


async def test_direct_internal_request_never_reaches_the_transport() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), event_hooks={"request": [guard_request]}
    )
    async with client:
        with pytest.raises(BlockedAddressError):
            await client.get("http://169.254.169.254/latest/meta-data/")
    assert calls == 0


# --- integración con el health-check ----------------------------------------


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1:6379/", "http://169.254.169.254/latest/meta-data/", "http://[::1]:8000/x"],
)
async def test_health_check_marks_internal_urls_as_not_alive(url: str) -> None:
    result = await check_stream_alive(url, timeout_s=2.0)

    assert result.alive is False
    assert result.status_code is None  # nunca se conectó: sin fuga del estado interno
    assert result.error is not None
    assert "non-public" in result.error
