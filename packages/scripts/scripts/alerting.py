"""Telegram alerting with Redis-backed dedup.

Two entry points:

* `Alerter.from_env(required=True)` for commands whose whole purpose is
  alerting (`watchdog`): missing credentials raise at startup, silently
  disabled alerting is the failure mode this exists to prevent.
* `notify_once` / `resolve_once` for best-effort calls embedded in other jobs
  (health-check, sync): they never raise and are no-ops without credentials.

Per alert key we keep two Redis entries: `alert:active:<key>` (no TTL, so a
later `resolve` knows an alert is open) and `alert:cd:<key>` (cooldown, so a
long outage re-notifies every `cooldown_s` instead of every run). Redis is
optional: if it is unreachable we send without dedup rather than drop alerts.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, cast

import httpx
from redis.asyncio import Redis

from scripts.logging import get_logger

if TYPE_CHECKING:
    from types import TracebackType

log = get_logger("alerting")

DEFAULT_COOLDOWN_S = 6 * 3600
TELEGRAM_API = os.environ.get("TELEGRAM_API_URL", "https://api.telegram.org")
MAX_MESSAGE_LEN = 4000  # Telegram hard limit is 4096 chars


class _TokenLeakFilter(logging.Filter):
    """httpx logs full request URLs at INFO; Telegram puts the bot token in the path."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Host-independent on purpose: TELEGRAM_API_URL can point elsewhere.
        msg = record.getMessage()
        return not ("/bot" in msg and "/sendMessage" in msg)


logging.getLogger("httpx").addFilter(_TokenLeakFilter())


class KeyValueStore(Protocol):
    async def get(self, key: str) -> bytes | str | None: ...
    async def set(
        self,
        key: str,
        value: str,
        *,
        nx: bool = False,
        ex: int | None = None,
    ) -> object: ...
    async def delete(self, *keys: str) -> object: ...
    async def exists(self, *keys: str) -> int: ...


@dataclass(frozen=True)
class AlertSettings:
    token: str
    chat_id: str


def load_alert_settings(*, required: bool) -> AlertSettings | None:
    token = os.environ.get("TELEGRAM_ALERT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_ALERT_CHAT_ID", "").strip()
    if token and chat_id:
        return AlertSettings(token=token, chat_id=chat_id)
    if required:
        msg = "TELEGRAM_ALERT_TOKEN y TELEGRAM_ALERT_CHAT_ID son obligatorios para este comando"
        raise ValueError(msg)
    return None


def _make_redis() -> KeyValueStore | None:
    url = os.environ.get("REDIS_URL")
    if not url:
        return None
    return cast("KeyValueStore", Redis.from_url(url, decode_responses=True))


class Alerter:
    def __init__(
        self,
        settings: AlertSettings | None,
        *,
        store: KeyValueStore | None = None,
        client: httpx.AsyncClient | None = None,
        cooldown_s: int = DEFAULT_COOLDOWN_S,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._own_client = client is None
        self._cooldown_s = cooldown_s

    @classmethod
    def from_env(cls, *, required: bool) -> Alerter:
        return cls(load_alert_settings(required=required), store=_make_redis())

    @property
    def store(self) -> KeyValueStore | None:
        return self._store

    @property
    def enabled(self) -> bool:
        return self._settings is not None

    async def __aenter__(self) -> Alerter:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._client is not None and self._own_client:
            await self._client.aclose()
        closer = getattr(self._store, "aclose", None)
        if closer is not None:
            await closer()

    async def _post(self, text: str) -> bool:
        if self._settings is None:
            return False
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        try:
            resp = await self._client.post(
                f"{TELEGRAM_API}/bot{self._settings.token}/sendMessage",
                json={
                    "chat_id": self._settings.chat_id,
                    "text": text[:MAX_MESSAGE_LEN],
                    "disable_web_page_preview": True,
                },
            )
        except httpx.HTTPError as exc:
            # str(exc) can embed the URL (with the token): log the type only.
            log.warning("telegram_send_failed", error_type=type(exc).__name__)
            return False
        if resp.status_code != httpx.codes.OK:
            log.warning("telegram_send_failed", status_code=resp.status_code)
            return False
        return True

    async def _store_op(self, op: str, *args: object, **kwargs: object) -> Any:  # noqa: ANN401
        if self._store is None:
            return None
        try:
            return await getattr(self._store, op)(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            log.warning("alert_store_unavailable", op=op, error_type=type(exc).__name__)
            return None

    async def _acquire_cooldown(self, key: str) -> bool:
        """True if no alert for `key` was sent within the cooldown (or no store)."""
        if self._store is None:
            return True
        try:
            return bool(
                await self._store.set(f"alert:cd:{key}", "1", nx=True, ex=self._cooldown_s),
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("alert_store_unavailable", op="set", error_type=type(exc).__name__)
            return True

    async def send(self, key: str, text: str) -> bool:
        """Send an alert unless one for `key` was sent within the cooldown."""
        if not self.enabled:
            log.warning("alerting_disabled", key=key)
            return False
        if not await self._acquire_cooldown(key):
            log.info("alert_suppressed", key=key)
            return False
        sent = await self._post(f"🚨 {text}")
        if sent:
            await self._store_op("set", f"alert:active:{key}", "1")
        else:
            await self._store_op("delete", f"alert:cd:{key}")  # let the next run retry
        log.info("alert_sent" if sent else "alert_not_sent", key=key)
        return sent

    async def resolve(self, key: str, text: str) -> bool:
        """Send a recovery message only if an alert for `key` is open."""
        if not self.enabled or self._store is None:
            return False
        if not await self._store_op("exists", f"alert:active:{key}"):
            return False
        sent = await self._post(f"✅ {text}")
        if sent:
            await self._store_op("delete", f"alert:active:{key}", f"alert:cd:{key}")
        return sent

    async def info(self, text: str) -> bool:
        """Unconditional informational message (daily summary)."""
        if not self.enabled:
            log.warning("alerting_disabled", key="info")
            return False
        return await self._post(f"📊 {text}")


async def notify_once(key: str, text: str) -> None:
    """Best-effort alert from inside another job. Never raises."""
    try:
        async with Alerter.from_env(required=False) as alerter:
            await alerter.send(key, text)
    except Exception as exc:  # noqa: BLE001
        log.warning("notify_failed", key=key, error_type=type(exc).__name__)


async def resolve_once(key: str, text: str) -> None:
    try:
        async with Alerter.from_env(required=False) as alerter:
            await alerter.resolve(key, text)
    except Exception as exc:  # noqa: BLE001
        log.warning("resolve_failed", key=key, error_type=type(exc).__name__)
