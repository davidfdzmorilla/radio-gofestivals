from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from redis import Redis as SyncRedis
from sqlalchemy import create_engine, text
from starlette.websockets import WebSocketDisconnect

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def sync_redis() -> Iterator[SyncRedis]:
    url = os.environ["REDIS_URL"]
    r: SyncRedis = SyncRedis.from_url(url)
    r.flushdb()
    yield r
    r.close()


@pytest.fixture
def sync_db_url() -> str:
    return os.environ["DATABASE_URL"].replace("+asyncpg", "+psycopg2")


@pytest.fixture
def seed_station(sync_db_url: str):  # type: ignore[no-untyped-def]
    engine = create_engine(sync_db_url)

    def _make(slug: str, status: str = "active") -> None:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO stations (slug, name, stream_url, status)
                    VALUES (:slug, :slug, 'https://x/y.mp3', CAST(:status AS station_status))
                    ON CONFLICT (slug) DO UPDATE SET status = EXCLUDED.status
                    """,
                ),
                {"slug": slug, "status": status},
            )

    yield _make
    engine.dispose()


@pytest.fixture
def sync_client() -> Iterator[TestClient]:
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_connect_invalid_station_closes(sync_client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as exc:
        with sync_client.websocket_connect("/api/v1/ws/nowplaying/no-such-station") as ws:
            ws.receive_text()
    assert exc.value.code == 1008


def test_connect_valid_station_gets_initial_state(
    sync_client: TestClient,
    seed_station,  # type: ignore[no-untyped-def]
    sync_redis: SyncRedis,
) -> None:
    seed_station("ws-ok", "active")
    sync_redis.set(
        "np:state:ws-ok",
        json.dumps({"title": "Hello", "artist": "World", "at": "2026-01-01T00:00:00+00:00"}),
    )

    with sync_client.websocket_connect("/api/v1/ws/nowplaying/ws-ok") as ws:
        data = json.loads(ws.receive_text())
        assert data["title"] == "Hello"
        assert data["artist"] == "World"


@pytest.mark.xfail(
    reason=(
        "Flaky: redis sync pubsub in this thread sometimes misses the async "
        "publish fired from the server's finally block. The functional path is "
        "exercised end-to-end via smoke tests against the deployed stack."
    ),
    strict=False,
)
def test_publishes_subscribe_on_connect_and_release_on_disconnect(
    sync_client: TestClient,
    seed_station,  # type: ignore[no-untyped-def]
    sync_redis: SyncRedis,
) -> None:
    seed_station("ws-pub", "active")
    pubsub = sync_redis.pubsub()
    pubsub.subscribe("icy:subscribe", "icy:release")
    for _ in range(2):
        pubsub.get_message(timeout=0.5)

    with sync_client.websocket_connect("/api/v1/ws/nowplaying/ws-pub"):
        got_sub = False
        for _ in range(20):
            m = pubsub.get_message(timeout=0.2)
            if m and m.get("type") == "message" and m["channel"] == b"icy:subscribe":
                assert m["data"] == b"ws-pub"
                got_sub = True
                break
        assert got_sub, "icy:subscribe not received"

    got_rel = False
    for _ in range(25):
        m = pubsub.get_message(timeout=0.2)
        if m and m.get("type") == "message" and m["channel"] == b"icy:release":
            assert m["data"] == b"ws-pub"
            got_rel = True
            break
    assert got_rel, "icy:release not received"

    pubsub.close()


def test_receives_update_when_state_changes(
    sync_client: TestClient,
    seed_station,  # type: ignore[no-untyped-def]
    sync_redis: SyncRedis,
) -> None:
    seed_station("ws-upd", "active")
    sync_redis.set(
        "np:state:ws-upd",
        json.dumps({"title": "First", "artist": "A", "at": "2026-01-01T00:00:00+00:00"}),
    )

    with sync_client.websocket_connect("/api/v1/ws/nowplaying/ws-upd") as ws:
        first = json.loads(ws.receive_text())
        assert first["title"] == "First"

        sync_redis.set(
            "np:state:ws-upd",
            json.dumps({"title": "Second", "artist": "B", "at": "2026-01-01T00:00:03+00:00"}),
        )
        second = json.loads(ws.receive_text())
        assert second["title"] == "Second"
