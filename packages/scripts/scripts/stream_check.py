"""Conservative stream liveness check.

Replaces the previous HEAD-based check that produced ~29% false
positives against Icecast/Shoutcast/Zeno servers. Those servers
notoriously reject HEAD with 400/405 even while serving audio fine.

The strategy here:
  - GET (not HEAD), `stream=True` so we never download more than the
    first ~1 KB even if the server ignores our Range hint
  - realistic User-Agent (some endpoints reject default httpx)
  - Icy-MetaData: 1 (declares us as a real audio client)
  - Origin header so servers emit Access-Control-Allow-Origin if they do CORS
  - follow_redirects=True (zeno.fm, radio.co, CDN chains are common)
  - on TLS or timeout failure, retry once with verify=False before
    giving up — many Icecast hosts ship outdated or self-signed certs
    while the audio itself is fine

Status code policy is deliberately conservative:
  >= 500     → dead
  404        → dead (URL is wrong, not a misbehaving HEAD handler)
  401/403    → ALIVE (auth required, stream exists)
  other 4xx  → ALIVE (Icecast 400 / 405 etc. - ambiguous, prefer FN over FP)
  200/206    → ALIVE if content-type is audio-ish OR icy-name header
               present; otherwise still ALIVE conservatively but logged

`alive` means "reachable from a server". `browser_playable` is stricter:
an HTTPS site's `<audio>` element ALSO needs valid TLS and no redirect to
http (mixed content). The verify=False retry that rescues `alive` is
exactly the case a browser rejects, so it forces `browser_playable=False`.
`cors_ok` is recorded separately (it no longer gates playback, only the
optional real spectrum analyzer).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

DEFAULT_TIMEOUT_S = 12.0
_USER_AGENT = "radio.gofestivals/1.0 (+https://radio.gofestivals.eu)"
_ORIGIN = "https://radio.gofestivals.eu"
_AUDIO_CT_PREFIXES = ("audio/", "application/ogg", "application/octet-stream")
_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Icy-MetaData": "1",
    "Range": "bytes=0-1023",
    "Accept": "*/*",
    "Origin": _ORIGIN,
}


@dataclass(frozen=True)
class StreamCheckResult:
    alive: bool
    status_code: int | None
    content_type: str | None
    error: str | None
    latency_ms: int
    # Server returned a permissive Access-Control-Allow-Origin.
    cors_ok: bool = False
    # Reachable AND playable by an <audio> element on an https site:
    # valid TLS and no redirect down to http. Dead streams are not playable.
    browser_playable: bool = False


def _truncate(msg: str, limit: int = 200) -> str:
    return msg if len(msg) <= limit else msg[:limit]


_CLIENT_ERROR = 400
_NOT_FOUND = 404
_SERVER_ERROR = 500


def _classify(status: int, ctype: str, icy_name: str | None) -> tuple[bool, str | None]:
    """Map an HTTP response to (alive, note) per the conservative policy."""
    if status in (401, 403):
        return True, f"auth required (status {status}, assumed alive)"
    if status >= _SERVER_ERROR:
        return False, f"server error {status}"
    if status == _NOT_FOUND:
        return False, "not found 404"
    if _CLIENT_ERROR <= status < _SERVER_ERROR:
        return True, f"non-fatal {status} (ambiguous, assumed alive)"
    if status in (200, 206):
        if ctype.startswith(_AUDIO_CT_PREFIXES):
            return True, None
        if icy_name:
            return True, f"non-audio content-type but icy-name='{icy_name}'"
        return True, f"unexpected content-type '{ctype}', conservative=alive"
    return False, f"unhandled status {status}"


def _cors_permissive(acao: str) -> bool:
    value = acao.strip()
    return value == "*" or value.rstrip("/") == _ORIGIN


async def check_stream_alive(
    stream_url: str,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    verify_ssl: bool = True,
    tls_degraded: bool = False,
    client: httpx.AsyncClient | None = None,
) -> StreamCheckResult:
    """Check whether `stream_url` is currently serving audio.

    See module docstring for the policy. The `client` parameter lets
    tests inject an httpx.AsyncClient with a MockTransport. `tls_degraded`
    is set internally when we fall back to verify=False after a real
    certificate failure — that outcome is fatal for a browser.
    """
    close_client = client is None
    hc = client or httpx.AsyncClient(
        timeout=timeout_s,
        follow_redirects=True,
        verify=verify_ssl,
        headers=_HEADERS,
    )

    start = time.monotonic()
    try:
        async with hc.stream("GET", stream_url, headers=_HEADERS) as response:
            latency_ms = int((time.monotonic() - start) * 1000)
            status = response.status_code
            ctype = response.headers.get("content-type", "").lower()
            acao = response.headers.get("access-control-allow-origin", "")
            cors_ok = _cors_permissive(acao)
            final_url = str(response.url)
            mixed_content = stream_url.lower().startswith(
                "https://",
            ) and final_url.lower().startswith("http://")

            alive, note = _classify(status, ctype, response.headers.get("icy-name"))
            browser_playable = alive and not mixed_content and not tls_degraded

            notes = [note] if note else []
            if mixed_content:
                notes.append("mixed-content: redirects to http (browser-blocked)")
            if tls_degraded and alive:
                notes.append("invalid TLS cert (browser-blocked)")

            return StreamCheckResult(
                alive=alive,
                status_code=status,
                content_type=ctype,
                error="; ".join(notes) or None,
                latency_ms=latency_ms,
                cors_ok=cors_ok,
                browser_playable=browser_playable,
            )

    except httpx.TimeoutException:
        if verify_ssl:
            # Generic retry (a slow first byte during TLS setup is common).
            # Not flagged as tls_degraded: a stream that eventually answers
            # is browser-playable.
            return await check_stream_alive(
                stream_url,
                timeout_s=timeout_s,
                verify_ssl=False,
                client=None,
            )
        return StreamCheckResult(
            alive=False,
            status_code=None,
            content_type=None,
            error=f"timeout after {timeout_s}s",
            latency_ms=int(timeout_s * 1000),
        )

    except httpx.ConnectError as exc:
        msg = str(exc)
        if "CERTIFICATE_VERIFY_FAILED" in msg and verify_ssl:
            # Cert genuinely fails verification: a browser blocks it. Retry
            # only to learn whether audio exists at all, but mark it as not
            # browser-playable.
            return await check_stream_alive(
                stream_url,
                timeout_s=timeout_s,
                verify_ssl=False,
                tls_degraded=True,
                client=None,
            )
        return StreamCheckResult(
            alive=False,
            status_code=None,
            content_type=None,
            error=f"connect error: {_truncate(msg)}",
            latency_ms=0,
        )

    except httpx.HTTPError as exc:
        return StreamCheckResult(
            alive=False,
            status_code=None,
            content_type=None,
            error=f"{type(exc).__name__}: {_truncate(str(exc))}",
            latency_ms=0,
        )

    finally:
        if close_client:
            await hc.aclose()
