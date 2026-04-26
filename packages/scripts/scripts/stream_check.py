"""Conservative stream liveness check.

Replaces the previous HEAD-based check that produced ~29% false
positives against Icecast/Shoutcast/Zeno servers. Those servers
notoriously reject HEAD with 400/405 even while serving audio fine.

The strategy here:
  - GET (not HEAD), `stream=True` so we never download more than the
    first ~1 KB even if the server ignores our Range hint
  - realistic User-Agent (some endpoints reject default httpx)
  - Icy-MetaData: 1 (declares us as a real audio client)
  - follow_redirects=True (zeno.fm, radio.co, CDN chains are common)
  - on TLS or timeout failure, retry once with verify=False before
    giving up — many Icecast hosts ship outdated or self-signed certs
    while the audio itself is fine

Status code policy is deliberately conservative:
  >= 500     → dead
  404        → dead (URL is wrong, not a misbehaving HEAD handler)
  401/403    → ALIVE (auth required, stream exists)
  other 4xx  → ALIVE (Icecast 400 / 405 etc. – ambiguous, prefer FN over FP)
  200/206    → ALIVE if content-type is audio-ish OR icy-name header
               present; otherwise still ALIVE conservatively but logged
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

DEFAULT_TIMEOUT_S = 12.0
_USER_AGENT = "radio.gofestivals/1.0 (+https://radio.gofestivals.eu)"
_AUDIO_CT_PREFIXES = ("audio/", "application/ogg", "application/octet-stream")
_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Icy-MetaData": "1",
    "Range": "bytes=0-1023",
    "Accept": "*/*",
}


@dataclass(frozen=True)
class StreamCheckResult:
    alive: bool
    status_code: int | None
    content_type: str | None
    error: str | None
    latency_ms: int


def _truncate(msg: str, limit: int = 200) -> str:
    return msg if len(msg) <= limit else msg[:limit]


async def check_stream_alive(
    stream_url: str,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    verify_ssl: bool = True,
    client: httpx.AsyncClient | None = None,
) -> StreamCheckResult:
    """Check whether `stream_url` is currently serving audio.

    See module docstring for the policy. The `client` parameter lets
    tests inject an httpx.AsyncClient with a MockTransport.
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

            if status in (401, 403):
                return StreamCheckResult(
                    alive=True, status_code=status, content_type=ctype,
                    error=f"auth required (status {status}, assumed alive)",
                    latency_ms=latency_ms,
                )

            if status >= 500:
                return StreamCheckResult(
                    alive=False, status_code=status, content_type=ctype,
                    error=f"server error {status}",
                    latency_ms=latency_ms,
                )

            if status == 404:
                return StreamCheckResult(
                    alive=False, status_code=status, content_type=ctype,
                    error="not found 404",
                    latency_ms=latency_ms,
                )

            if 400 <= status < 500:
                return StreamCheckResult(
                    alive=True, status_code=status, content_type=ctype,
                    error=f"non-fatal {status} (ambiguous, assumed alive)",
                    latency_ms=latency_ms,
                )

            if status in (200, 206):
                if ctype.startswith(_AUDIO_CT_PREFIXES):
                    return StreamCheckResult(
                        alive=True, status_code=status, content_type=ctype,
                        error=None, latency_ms=latency_ms,
                    )
                icy_name = response.headers.get("icy-name")
                if icy_name:
                    return StreamCheckResult(
                        alive=True, status_code=status, content_type=ctype,
                        error=f"non-audio content-type but icy-name='{icy_name}'",
                        latency_ms=latency_ms,
                    )
                return StreamCheckResult(
                    alive=True, status_code=status, content_type=ctype,
                    error=f"unexpected content-type '{ctype}', conservative=alive",
                    latency_ms=latency_ms,
                )

            return StreamCheckResult(
                alive=False, status_code=status, content_type=ctype,
                error=f"unhandled status {status}",
                latency_ms=latency_ms,
            )

    except httpx.TimeoutException:
        if verify_ssl:
            return await check_stream_alive(
                stream_url, timeout_s=timeout_s, verify_ssl=False,
            )
        return StreamCheckResult(
            alive=False, status_code=None, content_type=None,
            error=f"timeout after {timeout_s}s",
            latency_ms=int(timeout_s * 1000),
        )

    except httpx.ConnectError as exc:
        msg = str(exc)
        if "CERTIFICATE_VERIFY_FAILED" in msg and verify_ssl:
            return await check_stream_alive(
                stream_url, timeout_s=timeout_s, verify_ssl=False,
            )
        return StreamCheckResult(
            alive=False, status_code=None, content_type=None,
            error=f"connect error: {_truncate(msg)}",
            latency_ms=0,
        )

    except httpx.HTTPError as exc:
        return StreamCheckResult(
            alive=False, status_code=None, content_type=None,
            error=f"{type(exc).__name__}: {_truncate(str(exc))}",
            latency_ms=0,
        )

    finally:
        if close_client:
            await hc.aclose()
