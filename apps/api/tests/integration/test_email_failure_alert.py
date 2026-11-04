from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.redis import close_redis, init_redis
from app.services import alerting
from app.services.email_resend import send_email

RESEND_403 = {
    "message": "The davidfdzmorilla.dev domain is not verified.",
    "name": "validation_error",
    "statusCode": 403,
}


@pytest.fixture
async def redis_ready() -> Any:
    init_redis(get_settings())
    try:
        yield
    finally:
        await close_redis()


@pytest.fixture
def telegram_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Route Resend to a 403 and Telegram to a recorder; return the Telegram payloads."""
    calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.resend.com":
            return httpx.Response(403, json=RESEND_403)
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True})

    real_client = httpx.AsyncClient

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        return real_client(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr("app.services.email_resend.httpx.AsyncClient", factory)
    monkeypatch.setattr("app.services.alerting.httpx.AsyncClient", factory)
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("TELEGRAM_ALERT_TOKEN", "123:secret-token")
    monkeypatch.setenv("TELEGRAM_ALERT_CHAT_ID", "42")
    return calls


async def test_resend_failure_alerts_without_recipient(
    redis_ready: None,
    telegram_calls: list[dict[str, Any]],
) -> None:
    sent = await send_email(to="someone@example.com", subject="Hi", text="body")

    assert sent is False
    assert len(telegram_calls) == 1
    text = telegram_calls[0]["text"]
    assert telegram_calls[0]["chat_id"] == "42"
    assert "403" in text
    assert "domain is not verified" in text
    assert "someone@example.com" not in text


async def test_repeated_failures_alert_once_within_cooldown(
    redis_ready: None,
    telegram_calls: list[dict[str, Any]],
) -> None:
    for _ in range(3):
        await send_email(to="a@example.com", subject="Hi", text="body")

    assert len(telegram_calls) == 1


async def test_missing_api_key_alerts(
    redis_ready: None,
    telegram_calls: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    assert await send_email(to="a@example.com", subject="Hi", text="body") is False
    assert len(telegram_calls) == 1
    assert "RESEND_API_KEY" in telegram_calls[0]["text"]


async def test_alert_failure_never_breaks_email_flow(
    redis_ready: None,
    telegram_calls: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom(*_: object, **__: object) -> bool:
        msg = "telegram down"
        raise RuntimeError(msg)

    monkeypatch.setattr(alerting, "_acquire_cooldown", boom)

    assert await send_email(to="a@example.com", subject="Hi", text="body") is False


async def test_telegram_failure_releases_cooldown_for_retry(
    redis_ready: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_ALERT_TOKEN", "123:secret-token")
    monkeypatch.setenv("TELEGRAM_ALERT_CHAT_ID", "42")
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda _r: httpx.Response(400, json={"ok": False}))
    monkeypatch.setattr(
        "app.services.alerting.httpx.AsyncClient",
        lambda *a, **k: real_client(*a, transport=transport, **k),
    )

    assert await alerting.notify("k", "x") is False

    redis: Redis[str] = Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        assert await redis.exists("alert:cd:k") == 0
    finally:
        await redis.aclose()
