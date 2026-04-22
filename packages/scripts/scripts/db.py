from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.split("#", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _resolve_database_url() -> str:
    if "DATABASE_URL" in os.environ:
        return os.environ["DATABASE_URL"]
    here = Path(__file__).resolve()
    root = here.parents[3]
    for candidate in (root / ".env.local", root / ".env", root / "apps/api/.env"):
        _load_env_file(candidate)
        if "DATABASE_URL" in os.environ:
            return os.environ["DATABASE_URL"]
    msg = "DATABASE_URL no encontrado en env ni en .env/.env.local del repo"
    raise RuntimeError(msg)


def make_engine() -> AsyncEngine:
    return create_async_engine(_resolve_database_url(), pool_pre_ping=True)


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
