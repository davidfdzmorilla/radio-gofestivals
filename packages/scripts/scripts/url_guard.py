"""Bloquea conexiones salientes a direcciones no públicas (SSRF).

Las `stream_url` vienen de Radio-Browser, un tercero: cualquiera puede dar de
alta una emisora con `http://redis:6379/`, `http://169.254.169.254/...` o una
URL pública que redirija a una interna. El worker y el health-check corren en
la red interna del compose, con Postgres y Redis al alcance.

`guard_request` se engancha como `event_hooks={"request": [guard_request]}`: httpx
lo ejecuta en cada petición, también en cada salto de redirección.

Límite conocido: se resuelve el DNS aquí y httpx vuelve a resolverlo al
conectar, así que un DNS malicioso con TTL 0 (rebinding) podría cambiar de
respuesta entre ambos. Cerrarlo del todo exige fijar la IP en el backend de red.

Copia idéntica en `icy_worker/url_guard.py` y `scripts/url_guard.py`: los dos
paquetes se construyen en imágenes separadas y no comparten código. Si cambias
uno, cambia el otro (ADR 008).
"""

from __future__ import annotations

import asyncio
import ipaddress
import os
import socket

import httpx

_ALLOW_ENV = "ALLOW_PRIVATE_STREAM_HOSTS"


class BlockedAddressError(httpx.RequestError):
    """La URL apunta (directa o por DNS) a una dirección no pública."""


def _allow_private() -> bool:
    return os.environ.get(_ALLOW_ENV, "").strip().lower() in {"1", "true", "yes"}


def is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped  # ::ffff:10.0.0.1 es la 10.0.0.1
    return ip.is_global and not ip.is_multicast


async def _resolve(host: str, port: int) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return [str(info[4][0]) for info in infos]


async def assert_public_url(url: str, *, request: httpx.Request | None = None) -> None:
    """Lanza `BlockedAddressError` si algún destino de `url` no es público."""
    if _allow_private():
        return
    parsed = httpx.URL(url)
    host = parsed.host
    if not host:
        raise BlockedAddressError("url without host", request=request)

    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            resolved = await _resolve(host, port)
        except OSError:
            # No resuelve: la conexión real fallará sola con su error normal.
            return
        addresses = [ipaddress.ip_address(addr.split("%", 1)[0]) for addr in resolved]

    for ip in addresses:
        # Cualquier destino interno basta: un nombre con una A pública y otra
        # privada es justo lo que usa un atacante.
        if not is_public_ip(ip):
            msg = f"non-public address {ip} for host {host}"
            raise BlockedAddressError(msg, request=request)


async def guard_request(request: httpx.Request) -> None:
    await assert_public_url(str(request.url), request=request)
