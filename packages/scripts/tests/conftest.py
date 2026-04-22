from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://radio:radio_dev_password@localhost:5433/radio",
)
os.environ["RB_USER_AGENT"] = os.environ.get(
    "RB_USER_AGENT", "radio.gofestivals/test (admin@gofestivals.eu)",
)
os.environ["LOG_LEVEL"] = os.environ.get("LOG_LEVEL", "WARNING")


@pytest_asyncio.fixture
async def maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    m = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield m
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(
    maker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with maker() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def _reset_tables(maker: async_sessionmaker[AsyncSession]) -> AsyncIterator[None]:
    async with maker() as session:
        await session.execute(
            text(
                "TRUNCATE curation_log, now_playing, station_genres, stations, admins "
                "RESTART IDENTITY CASCADE",
            ),
        )
        await session.commit()
    yield
