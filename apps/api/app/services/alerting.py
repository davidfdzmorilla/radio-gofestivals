"""Best-effort Telegram alerts from the API (ADR 006).

Same env vars, Redis keys and cooldown semantics as `packages/scripts/scripts/alerting.py`,
so an alert key shared between both sides dedups across them. Never raises: an alert that
cannot be sent must not break the request that triggered it.
"""

from __future__ import annotations

import logging
import os

import httpx

from app.core.logging import get_logger
from app.core.redis import get_redis

log = get_logger("app.alerting")

TELEGRAM_API = os.environ.get("TELEGRAM_API_URL", "https://api.telegram.org")
COOLDOWN_S = 6 * 3600
MAX_MESSAGE_LEN = 4000  # Telegram hard limit is 4096 chars


class _TokenLeakFilter(logging.Filter):
    """httpx logs full request URLs at INFO; Telegram puts the bot token in the path."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not ("/bot" in msg and "/sendMessage" in msg)


logging.getLogger("httpx").addFilter(_TokenLeakFilter())


async def _acquire_cooldown(key: str) -> bool:
    """True if no alert for `key` was sent within the cooldown (or Redis is down)."""
    try:
        return bool(await get_redis().set(f"alert:cd:{key}", "1", nx=True, ex=COOLDOWN_S))
    except Exception as exc:  # noqa: BLE001
        log.warning("alert_store_unavailable", error_type=type(exc).__name__)
        return True


async def _release(key: str, *, sent: bool) -> None:
    try:
        redis = get_redis()
        if sent:
            await redis.set(f"alert:active:{key}", "1")
        else:
            await redis.delete(f"alert:cd:{key}")  # let the next failure retry
    except Exception as exc:  # noqa: BLE001
        log.warning("alert_store_unavailable", error_type=type(exc).__name__)


async def notify(key: str, text: str) -> bool:
    """Send a Telegram alert unless one for `key` went out within the cooldown."""
    try:
        token = os.environ.get("TELEGRAM_ALERT_TOKEN", "").strip()
        chat_id = os.environ.get("TELEGRAM_ALERT_CHAT_ID", "").strip()
        if not (token and chat_id):
            log.warning("alerting_disabled", key=key)
            return False
        if not await _acquire_cooldown(key):
            log.info("alert_suppressed", key=key)
            return False

        sent = False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{TELEGRAM_API}/bot{token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": f"🚨 {text}"[:MAX_MESSAGE_LEN],
                        "disable_web_page_preview": True,
                    },
                )
            sent = resp.status_code == httpx.codes.OK
            if not sent:
                log.warning("telegram_send_failed", status_code=resp.status_code)
        except httpx.HTTPError as exc:
            # str(exc) can embed the URL (with the token): log the type only.
            log.warning("telegram_send_failed", error_type=type(exc).__name__)

        await _release(key, sent=sent)
        log.info("alert_sent" if sent else "alert_not_sent", key=key)
    except Exception as exc:  # noqa: BLE001
        log.warning("notify_failed", key=key, error_type=type(exc).__name__)
        return False
    return sent
