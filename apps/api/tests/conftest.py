from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://radio:radio_dev_password@localhost:5433/radio",
)
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")
os.environ["JWT_SECRET"] = "test_secret"
os.environ["RB_USER_AGENT"] = "radio.gofestivals/test"
os.environ["ENV"] = "dev"


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    from app.core.config import get_settings
    from app.core.db import dispose_engine, init_engine
    from app.core.redis import close_redis, init_redis
    from app.main import app

    settings = get_settings()
    init_engine(settings)
    init_redis(settings)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        await dispose_engine()
        await close_redis()


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _reset_state(db_session: AsyncSession) -> AsyncIterator[None]:
    from redis.asyncio import Redis
    from sqlalchemy import text

    await db_session.execute(
        text(
            "TRUNCATE password_reset_tokens, user_votes, user_favorites, "
            "users, curation_log, now_playing, station_genres, stations, "
            "admins RESTART IDENTITY CASCADE",
        ),
    )
    await db_session.execute(
        text(
            """
            DELETE FROM genres WHERE slug NOT IN (
                'techno','house','deep-house','tech-house','trance','progressive',
                'dnb','liquid-dnb','dubstep','ambient','hardstyle','breakbeat',
                'electronic','minimal'
            )
            """,
        ),
    )
    await db_session.commit()

    redis: Redis[str] = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    await redis.flushdb()
    await redis.aclose()
    yield


@pytest_asyncio.fixture
async def create_genre(db_session: AsyncSession):  # type: ignore[no-untyped-def]
    from sqlalchemy import text

    async def _make(
        slug: str,
        name: str,
        parent_id: int | None = None,
        color_hex: str = "#8B4EE8",
    ) -> int:
        result = await db_session.execute(
            text(
                """
                INSERT INTO genres (slug, name, parent_id, color_hex)
                VALUES (:slug, :name, :parent_id, :color_hex)
                ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
                """,
            ),
            {"slug": slug, "name": name, "parent_id": parent_id, "color_hex": color_hex},
        )
        await db_session.commit()
        return int(result.scalar_one())

    return _make


@pytest_asyncio.fixture
async def create_station(db_session: AsyncSession):  # type: ignore[no-untyped-def]
    from sqlalchemy import text

    async def _make(
        *,
        slug: str,
        name: str | None = None,
        country_code: str | None = "ES",
        city: str | None = "Madrid",
        codec: str = "mp3",
        bitrate: int = 128,
        curated: bool = True,
        quality_score: int = 80,
        status: str = "active",
        stream_url: str = "https://example.com/stream.mp3",
        lat: float | None = None,
        lng: float | None = None,
        genre_slugs: list[str] | None = None,
    ) -> uuid.UUID:
        geo_sql = "NULL"
        params: dict[str, object] = {
            "slug": slug,
            "name": name or slug.replace("-", " ").title(),
            "country_code": country_code,
            "city": city,
            "codec": codec,
            "bitrate": bitrate,
            "curated": curated,
            "quality_score": quality_score,
            "status": status,
            "stream_url": stream_url,
        }
        if lat is not None and lng is not None:
            geo_sql = "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography"
            params["lat"] = lat
            params["lng"] = lng

        stmt = text(
            f"""
            INSERT INTO stations (
                slug, name, stream_url, country_code, city, codec, bitrate,
                curated, quality_score, status, geo
            ) VALUES (
                :slug, :name, :stream_url, :country_code, :city, :codec, :bitrate,
                :curated, :quality_score, CAST(:status AS station_status), {geo_sql}
            ) RETURNING id
            """,  # noqa: S608
        )
        result = await db_session.execute(stmt, params)
        station_id = uuid.UUID(str(result.scalar_one()))

        if genre_slugs:
            await db_session.execute(
                text(
                    """
                    INSERT INTO station_genres (station_id, genre_id, source, confidence)
                    SELECT :sid, g.id, 'manual', 100
                    FROM genres g WHERE g.slug = ANY(:slugs)
                    ON CONFLICT DO NOTHING
                    """,
                ),
                {"sid": station_id, "slugs": genre_slugs},
            )
        await db_session.commit()
        return station_id

    return _make
