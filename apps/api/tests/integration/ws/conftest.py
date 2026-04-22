from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, text

# Override: los tests WS son sync (TestClient). El autouse async del conftest
# raíz puede deadlockear con el loop interno del TestClient, así que aquí
# hacemos un reset sync directo.


@pytest_asyncio.fixture(autouse=True)
async def _reset_state() -> AsyncIterator[None]:  # noqa: PT004
    yield


@pytest.fixture(autouse=True)
def _sync_reset() -> Iterator[None]:
    url = os.environ["DATABASE_URL"].replace("+asyncpg", "+psycopg2")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE curation_log, now_playing, station_genres, stations, admins "
                "RESTART IDENTITY CASCADE",
            ),
        )
        conn.execute(
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
    engine.dispose()
    yield
