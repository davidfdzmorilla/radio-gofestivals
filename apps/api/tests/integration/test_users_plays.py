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
    """Mint a JWT for a freshly-inserted user, same helper as the plays
    endpoint tests use — avoids the .local TLD rejection in the public
    auth endpoint.
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


async def _seed_plays(
    session: AsyncSession,
    *,
    station_slug: str,
    user_id: uuid.UUID | None = None,
    client_id: uuid.UUID | None = None,
    played_at: str | None = None,
) -> None:
    """Direct INSERT to seed plays in arbitrary days for merge tests.

    Bypasses the endpoint because the endpoint always uses now() for
    played_at, which we can't override to test cross-day scenarios.
    """
    placeholder = "now()" if played_at is None else f"TIMESTAMPTZ '{played_at}'"
    if user_id is not None:
        await session.execute(
            text(
                f"INSERT INTO station_plays (station_id, user_id, played_at) "  # noqa: S608
                f"SELECT id, :uid, {placeholder} FROM stations WHERE slug = :s",
            ),
            {"uid": user_id, "s": station_slug},
        )
    else:
        await session.execute(
            text(
                f"INSERT INTO station_plays (station_id, client_id, played_at) "  # noqa: S608
                f"SELECT id, :cid, {placeholder} FROM stations WHERE slug = :s",
            ),
            {"cid": client_id, "s": station_slug},
        )
    await session.commit()


async def _plays_for(
    session: AsyncSession, *, user_id: uuid.UUID | None = None,
    client_id: uuid.UUID | None = None,
) -> int:
    if user_id is not None:
        result = await session.execute(
            text("SELECT COUNT(*) FROM station_plays WHERE user_id = :uid"),
            {"uid": user_id},
        )
    else:
        result = await session.execute(
            text(
                "SELECT COUNT(*) FROM station_plays WHERE client_id = :cid",
            ),
            {"cid": client_id},
        )
    return int(result.scalar_one())


async def test_merge_moves_anon_plays_to_user(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
    make_token: Callable[[], Awaitable[tuple[uuid.UUID, str]]],
) -> None:
    await create_station(slug="m-a", genre_slugs=["techno"])
    await create_station(slug="m-b", genre_slugs=["techno"])
    cid = uuid.uuid4()
    await _seed_plays(db_session, station_slug="m-a", client_id=cid)
    await _seed_plays(db_session, station_slug="m-b", client_id=cid)

    user_id, token = await make_token()
    r = await client.post(
        "/api/v1/me/plays/merge",
        json={"client_id": str(cid)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"merged": 2, "dropped_conflicts": 0}
    assert await _plays_for(db_session, user_id=user_id) == 2
    assert await _plays_for(db_session, client_id=cid) == 0


async def test_merge_drops_same_day_conflicts(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
    make_token: Callable[[], Awaitable[tuple[uuid.UUID, str]]],
) -> None:
    """If the user already played a station today, the matching anon
    row gets deleted on merge — the user's day-play is already there.
    """
    await create_station(slug="m-c", genre_slugs=["techno"])
    await create_station(slug="m-d", genre_slugs=["techno"])
    user_id, token = await make_token()
    cid = uuid.uuid4()

    # User already played m-c today. Anon also played m-c today (would conflict).
    await _seed_plays(db_session, station_slug="m-c", user_id=user_id)
    await _seed_plays(db_session, station_slug="m-c", client_id=cid)
    # Anon also played m-d today (no conflict).
    await _seed_plays(db_session, station_slug="m-d", client_id=cid)

    r = await client.post(
        "/api/v1/me/plays/merge",
        json={"client_id": str(cid)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.json() == {"merged": 1, "dropped_conflicts": 1}
    # User now has m-c (their original) + m-d (merged from anon).
    assert await _plays_for(db_session, user_id=user_id) == 2
    assert await _plays_for(db_session, client_id=cid) == 0


async def test_merge_unknown_client_id_is_noop(
    client: AsyncClient,
    make_token: Callable[[], Awaitable[tuple[uuid.UUID, str]]],
) -> None:
    _, token = await make_token()
    r = await client.post(
        "/api/v1/me/plays/merge",
        json={"client_id": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json() == {"merged": 0, "dropped_conflicts": 0}


async def test_merge_requires_auth(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/me/plays/merge", json={"client_id": str(uuid.uuid4())},
    )
    assert r.status_code in {401, 403}


async def test_export_returns_user_plays(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
    make_token: Callable[[], Awaitable[tuple[uuid.UUID, str]]],
) -> None:
    await create_station(
        slug="exp-a", name="Export A", genre_slugs=["techno"],
    )
    await create_station(
        slug="exp-b", name="Export B", genre_slugs=["house"],
    )
    user_id, token = await make_token()
    await _seed_plays(db_session, station_slug="exp-a", user_id=user_id)
    await _seed_plays(db_session, station_slug="exp-b", user_id=user_id)

    r = await client.get(
        "/api/v1/me/plays/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["id"] == str(user_id)
    assert body["user"]["email"].endswith("@example.com")
    slugs = {p["station_slug"] for p in body["plays"]}
    assert slugs == {"exp-a", "exp-b"}
    assert {p["station_name"] for p in body["plays"]} == {"Export A", "Export B"}


async def test_export_excludes_other_users(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
    make_token: Callable[[], Awaitable[tuple[uuid.UUID, str]]],
) -> None:
    await create_station(slug="shared", genre_slugs=["techno"])
    me_id, my_token = await make_token()
    other_id, _ = await make_token()
    await _seed_plays(db_session, station_slug="shared", user_id=me_id)
    await _seed_plays(db_session, station_slug="shared", user_id=other_id)

    r = await client.get(
        "/api/v1/me/plays/export",
        headers={"Authorization": f"Bearer {my_token}"},
    )
    assert r.status_code == 200
    assert len(r.json()["plays"]) == 1


async def test_export_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/api/v1/me/plays/export")
    assert r.status_code in {401, 403}


async def test_erase_deletes_user_plays_and_decrements_counter(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
    make_token: Callable[[], Awaitable[tuple[uuid.UUID, str]]],
) -> None:
    await create_station(slug="era-a", genre_slugs=["techno"])
    await create_station(slug="era-b", genre_slugs=["techno"])
    user_id, token = await make_token()
    await _seed_plays(db_session, station_slug="era-a", user_id=user_id)
    await _seed_plays(db_session, station_slug="era-b", user_id=user_id)

    # Counters before
    before_a = (
        await db_session.execute(
            text(
                "SELECT local_plays_total FROM stations WHERE slug='era-a'",
            ),
        )
    ).scalar_one()
    assert int(before_a) == 1

    r = await client.post(
        "/api/v1/me/plays/erase",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json() == {"erased": 2}
    assert await _plays_for(db_session, user_id=user_id) == 0

    # DELETE trigger decremented the denormalized counter.
    after_a = (
        await db_session.execute(
            text(
                "SELECT local_plays_total FROM stations WHERE slug='era-a'",
            ),
        )
    ).scalar_one()
    assert int(after_a) == 0


async def test_erase_does_not_touch_other_users(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
    make_token: Callable[[], Awaitable[tuple[uuid.UUID, str]]],
) -> None:
    await create_station(slug="iso", genre_slugs=["techno"])
    me_id, my_token = await make_token()
    other_id, _ = await make_token()
    await _seed_plays(db_session, station_slug="iso", user_id=me_id)
    await _seed_plays(db_session, station_slug="iso", user_id=other_id)

    r = await client.post(
        "/api/v1/me/plays/erase",
        headers={"Authorization": f"Bearer {my_token}"},
    )
    assert r.json()["erased"] == 1
    assert await _plays_for(db_session, user_id=other_id) == 1


async def test_erase_requires_auth(client: AsyncClient) -> None:
    r = await client.post("/api/v1/me/plays/erase")
    assert r.status_code in {401, 403}
