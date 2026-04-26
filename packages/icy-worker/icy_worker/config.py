from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_env_files() -> None:
    here = Path(__file__).resolve()
    try:
        root = here.parents[3]
    except IndexError:
        return  # in container: env vars come from Docker environment
    for candidate in (root / ".env.local", root / ".env"):
        if not candidate.is_file():
            continue
        for raw in candidate.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.split("#", 1)[0].strip().strip('"').strip("'")
            os.environ.setdefault(key.strip(), value)


@dataclass(frozen=True)
class WorkerConfig:
    database_url: str
    redis_url: str
    user_agent: str
    ondemand_concurrency: int = 40
    ambient_concurrency: int = 10
    ondemand_grace_seconds: int = 60
    ondemand_timeout_seconds: int = 300
    ambient_interval_seconds: int = 60
    ambient_top_n: int = 50
    ambient_probe_timeout: float = 10.0


def _resolve_ondemand_concurrency() -> int:
    explicit = os.environ.get("ICY_ONDEMAND_CONCURRENCY")
    legacy = os.environ.get("ICY_CONCURRENCY")
    if explicit is not None:
        return int(explicit)
    if legacy is not None:
        import warnings

        warnings.warn(
            "ICY_CONCURRENCY is deprecated; use ICY_ONDEMAND_CONCURRENCY "
            "(+ ICY_AMBIENT_CONCURRENCY) instead. Using legacy value for ondemand.",
            DeprecationWarning,
            stacklevel=2,
        )
        return int(legacy)
    return 40


def load_config() -> WorkerConfig:
    _load_env_files()
    if "DATABASE_URL" not in os.environ:
        msg = "DATABASE_URL not set"
        raise RuntimeError(msg)
    if "REDIS_URL" not in os.environ:
        msg = "REDIS_URL not set"
        raise RuntimeError(msg)
    return WorkerConfig(
        database_url=os.environ["DATABASE_URL"],
        redis_url=os.environ["REDIS_URL"],
        user_agent=os.environ.get(
            "RB_USER_AGENT", "radio.gofestivals/icy-worker",
        ),
        ondemand_concurrency=_resolve_ondemand_concurrency(),
        ambient_concurrency=int(os.environ.get("ICY_AMBIENT_CONCURRENCY", "10")),
        ondemand_grace_seconds=int(os.environ.get("ICY_ONDEMAND_GRACE", "60")),
        ondemand_timeout_seconds=int(os.environ.get("ICY_ONDEMAND_TIMEOUT", "300")),
        ambient_interval_seconds=int(os.environ.get("ICY_AMBIENT_POLL_INTERVAL", "60")),
        ambient_top_n=int(os.environ.get("ICY_AMBIENT_TOP_N", "50")),
        ambient_probe_timeout=float(os.environ.get("ICY_AMBIENT_PROBE_TIMEOUT", "10")),
    )
