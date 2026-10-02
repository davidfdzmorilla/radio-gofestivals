from __future__ import annotations

import logging

import httpx
import pytest
import respx

from scripts.alerting import Alerter, AlertSettings, load_alert_settings

SETTINGS = AlertSettings(token="123:SECRET", chat_id="42")  # noqa: S106
URL = "https://api.telegram.org/bot123:SECRET/sendMessage"


class FakeStore:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def set(
        self,
        key: str,
        value: str,
        *,
        nx: bool = False,
        ex: int | None = None,
    ) -> bool | None:
        _ = ex
        if nx and key in self.data:
            return None
        self.data[key] = value
        return True

    async def delete(self, *keys: str) -> int:
        return sum(self.data.pop(k, None) is not None for k in keys)

    async def exists(self, *keys: str) -> int:
        return sum(k in self.data for k in keys)


@respx.mock
async def test_send_posts_to_telegram_and_marks_active() -> None:
    route = respx.post(URL).respond(200, json={"ok": True})
    store = FakeStore()
    async with Alerter(SETTINGS, store=store) as a:
        assert await a.send("k", "boom") is True
    body = route.calls.last.request.read().decode()
    assert '"chat_id":"42"' in body.replace(" ", "")
    assert "boom" in body
    assert "alert:active:k" in store.data


@respx.mock
async def test_second_alert_within_cooldown_is_suppressed() -> None:
    route = respx.post(URL).respond(200, json={"ok": True})
    store = FakeStore()
    async with Alerter(SETTINGS, store=store) as a:
        assert await a.send("k", "one") is True
        assert await a.send("k", "two") is False
    assert route.call_count == 1


@respx.mock
async def test_failed_send_releases_cooldown_so_next_run_retries(
    capfd: pytest.CaptureFixture[str],
) -> None:
    respx.post(URL).respond(400, json={"ok": False, "description": "Bad Request: chat not found"})
    store = FakeStore()
    async with Alerter(SETTINGS, store=store) as a:
        assert await a.send("k", "one") is False
    out = capfd.readouterr().out
    assert "chat not found" in out
    assert "SECRET" not in out
    assert "alert:cd:k" not in store.data
    assert "alert:active:k" not in store.data


@respx.mock
async def test_network_error_does_not_raise() -> None:
    respx.post(URL).mock(side_effect=httpx.ConnectTimeout("t"))
    async with Alerter(SETTINGS, store=FakeStore()) as a:
        assert await a.send("k", "one") is False


@respx.mock
async def test_resolve_only_when_alert_open() -> None:
    route = respx.post(URL).respond(200, json={"ok": True})
    store = FakeStore()
    async with Alerter(SETTINGS, store=store) as a:
        assert await a.resolve("k", "ok") is False  # nothing open
        await a.send("k", "boom")
        assert await a.resolve("k", "ok") is True
        assert await a.resolve("k", "ok") is False  # already closed
        # after resolve a new incident alerts again immediately
        assert await a.send("k", "boom again") is True
    assert route.call_count == 3


@respx.mock
async def test_sends_without_store() -> None:
    route = respx.post(URL).respond(200, json={"ok": True})
    async with Alerter(SETTINGS, store=None) as a:
        assert await a.send("k", "x") is True
        assert await a.send("k", "x") is True  # no dedup possible, but never dropped
    assert route.call_count == 2


async def test_disabled_alerter_is_noop() -> None:
    async with Alerter(None) as a:
        assert a.enabled is False
        assert await a.send("k", "x") is False
        assert await a.info("x") is False


def test_required_settings_fail_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_ALERT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_ALERT_CHAT_ID", raising=False)
    with pytest.raises(ValueError, match="TELEGRAM_ALERT_TOKEN"):
        load_alert_settings(required=True)
    assert load_alert_settings(required=False) is None


@respx.mock
async def test_bot_token_never_reaches_httpx_logs(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("scripts.alerting.TELEGRAM_API", "http://other-host.test")
    respx.post("http://other-host.test/bot123:SECRET/sendMessage").respond(200, json={"ok": True})
    with caplog.at_level(logging.INFO):
        async with Alerter(SETTINGS, store=FakeStore()) as a:
            await a.send("k", "boom")
    assert "SECRET" not in caplog.text
