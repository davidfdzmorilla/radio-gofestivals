from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest_asyncio
from sqlalchemy import text

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def make_token(db_session: AsyncSession):  # type: ignore[no-untyped-def]
    """Mint a JWT for a freshly-inserted user, bypassing the public auth
    endpoint (which currently rejects '.local' test emails via the
    email-validator drift). We only need a token that decodes back to a
    real users row.
    """
    from app.core.config import get_settings
    from app.core.security import issue_user_token

    counter = {"n": 0}

    async def _make() -> tuple[uuid.UUID, str]:
        counter["n"] += 1
        user_id = uuid.uuid4()
        email = f"plays-user-{counter['n']}@example.com"
        await db_session.execute(
            text(
                "INSERT INTO users (id, email, password_hash) "
                "VALUES (:id, :email, 'hash-not-checked-here')",
            ),
            {"id": user_id, "email": email},
        )
        await db_session.commit()
        settings = get_settings()
        token, _ = issue_user_token(user_id, email, settings)
        return user_id, token

    return _make


async def _plays_count(session: AsyncSession) -> int:
    row = (await session.execute(text("SELECT COUNT(*) FROM station_plays"))).scalar_one()
    return int(row)


async def _local_plays_total(session: AsyncSession, slug: str) -> int:
    row = (
        await session.execute(
            text("SELECT local_plays_total FROM stations WHERE slug = :s"),
            {"s": slug},
        )
    ).scalar_one()
    return int(row)


async def test_play_with_jwt_inserts_row_keyed_by_user_id(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
    make_token: Callable[[], Awaitable[tuple[uuid.UUID, str]]],
) -> None:
    await create_station(slug="play-target", genre_slugs=["techno"])
    user_id, token = await make_token()

    r = await client.post(
        "/api/v1/stations/play-target/play",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"accepted": True, "deduplicated": False}

    row = (
        await db_session.execute(
            text(
                "SELECT user_id, client_id FROM station_plays ORDER BY id DESC LIMIT 1",
            ),
        )
    ).first()
    assert row is not None
    assert uuid.UUID(str(row[0])) == user_id
    assert row[1] is None
    assert await _local_plays_total(db_session, "play-target") == 1


async def test_play_with_client_id_inserts_anonymous_row(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="anon-target", genre_slugs=["techno"])
    cid = uuid.uuid4()

    r = await client.post(
        "/api/v1/stations/anon-target/play",
        json={"client_id": str(cid)},
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"accepted": True, "deduplicated": False}

    row = (
        await db_session.execute(
            text(
                "SELECT user_id, client_id FROM station_plays ORDER BY id DESC LIMIT 1",
            ),
        )
    ).first()
    assert row is not None
    assert row[0] is None
    assert uuid.UUID(str(row[1])) == cid


async def test_play_jwt_wins_over_client_id_when_both_present(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
    make_token: Callable[[], Awaitable[tuple[uuid.UUID, str]]],
) -> None:
    await create_station(slug="dual-target", genre_slugs=["techno"])
    user_id, token = await make_token()
    cid = uuid.uuid4()

    r = await client.post(
        "/api/v1/stations/dual-target/play",
        json={"client_id": str(cid)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text

    row = (
        await db_session.execute(
            text(
                "SELECT user_id, client_id FROM station_plays ORDER BY id DESC LIMIT 1",
            ),
        )
    ).first()
    assert row is not None
    assert uuid.UUID(str(row[0])) == user_id
    # Body client_id is dropped — JWT identifies the actor.
    assert row[1] is None


async def test_play_dedups_same_identity_same_station_same_day(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="dedup-target", genre_slugs=["techno"])
    cid = uuid.uuid4()

    r1 = await client.post(
        "/api/v1/stations/dedup-target/play",
        json={"client_id": str(cid)},
    )
    r2 = await client.post(
        "/api/v1/stations/dedup-target/play",
        json={"client_id": str(cid)},
    )
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["deduplicated"] is False
    assert r2.json()["deduplicated"] is True

    assert await _plays_count(db_session) == 1
    assert await _local_plays_total(db_session, "dedup-target") == 1


async def test_play_different_identities_both_count(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="multi-target", genre_slugs=["techno"])
    cid1, cid2 = uuid.uuid4(), uuid.uuid4()

    await client.post(
        "/api/v1/stations/multi-target/play",
        json={"client_id": str(cid1)},
    )
    await client.post(
        "/api/v1/stations/multi-target/play",
        json={"client_id": str(cid2)},
    )

    assert await _plays_count(db_session) == 2
    assert await _local_plays_total(db_session, "multi-target") == 2


async def test_play_without_any_identity_returns_400(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="lonely", genre_slugs=["techno"])
    r = await client.post("/api/v1/stations/lonely/play", json={})
    assert r.status_code == 400
    assert r.json()["detail"] == "identity_required"


async def test_play_unknown_slug_returns_404(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/stations/does-not-exist/play",
        json={"client_id": str(uuid.uuid4())},
    )
    assert r.status_code == 404


async def test_play_works_against_hidden_station(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="ghost", genre_slugs=["techno"])
    await db_session.execute(
        text("UPDATE stations SET hidden = true WHERE slug = 'ghost'"),
    )
    await db_session.commit()

    r = await client.post(
        "/api/v1/stations/ghost/play",
        json={"client_id": str(uuid.uuid4())},
    )
    assert r.status_code == 200
    assert await _plays_count(db_session) == 1


async def test_play_invalid_client_id_returns_422(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="strict", genre_slugs=["techno"])
    r = await client.post(
        "/api/v1/stations/strict/play",
        json={"client_id": "not-a-uuid"},
    )
    assert r.status_code == 422


async def test_play_delete_decrements_local_plays_total(
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    """The DELETE trigger keeps the counter consistent so GDPR erasure
    of a user's plays doesn't leave the denormalized total off forever.
    """
    await create_station(slug="erasable", genre_slugs=["techno"])
    cid = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO station_plays (station_id, client_id) "
            "SELECT id, :cid FROM stations WHERE slug = 'erasable'",
        ),
        {"cid": cid},
    )
    await db_session.commit()
    assert await _local_plays_total(db_session, "erasable") == 1

    await db_session.execute(
        text("DELETE FROM station_plays WHERE client_id = :cid"),
        {"cid": cid},
    )
    await db_session.commit()
    assert await _local_plays_total(db_session, "erasable") == 0
