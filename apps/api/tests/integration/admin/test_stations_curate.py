from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

from app.services import genres as genres_service

if TYPE_CHECKING:
    from httpx import AsyncClient
    from pytest_mock import MockerFixture
    from sqlalchemy.ext.asyncio import AsyncSession


async def test_401_without_auth(client: AsyncClient, create_station) -> None:  # type: ignore[no-untyped-def]
    sid = await create_station(slug="pend", status="pending")
    resp = await client.put(
        f"/api/v1/admin/stations/{sid}/curate",
        json={"decision": "approve"},
    )
    assert resp.status_code == 401


async def test_approve_transitions_to_active_curated(
    logged_in_client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
    db_session: AsyncSession,
) -> None:
    sid = await create_station(slug="pend", status="pending", curated=False)

    resp = await logged_in_client.put(
        f"/api/v1/admin/stations/{sid}/curate",
        json={"decision": "approve", "quality_score": 85, "notes": "OK"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "active"
    assert body["curated"] is True
    assert body["log_id"] > 0

    row = (
        await db_session.execute(
            text("SELECT status::text, curated, quality_score FROM stations WHERE id = :id"),
            {"id": str(sid)},
        )
    ).first()
    assert row is not None
    assert row[0] == "active"
    assert row[1] is True
    assert row[2] == 85


async def test_reject_transitions_to_rejected(
    logged_in_client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
    db_session: AsyncSession,
) -> None:
    sid = await create_station(slug="pend", status="pending")
    resp = await logged_in_client.put(
        f"/api/v1/admin/stations/{sid}/curate",
        json={"decision": "reject", "notes": "Spam"},
    )
    assert resp.status_code == 200
    status_val = (
        await db_session.execute(
            text("SELECT status::text FROM stations WHERE id = :id"), {"id": str(sid)},
        )
    ).scalar_one()
    assert status_val == "rejected"


async def test_reclassify_replaces_genres(
    logged_in_client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
    db_session: AsyncSession,
) -> None:
    sid = await create_station(slug="pend", status="pending", genre_slugs=["techno"])
    house_id = (
        await db_session.execute(text("SELECT id FROM genres WHERE slug='house'"))
    ).scalar_one()
    dh_id = (
        await db_session.execute(text("SELECT id FROM genres WHERE slug='deep-house'"))
    ).scalar_one()

    resp = await logged_in_client.put(
        f"/api/v1/admin/stations/{sid}/curate",
        json={"decision": "reclassify", "genre_ids": [house_id, dh_id]},
    )
    assert resp.status_code == 200

    rows = (
        await db_session.execute(
            text(
                "SELECT g.slug, sg.source, sg.confidence FROM station_genres sg "
                "JOIN genres g ON g.id=sg.genre_id WHERE sg.station_id=:sid ORDER BY g.slug",
            ),
            {"sid": str(sid)},
        )
    ).all()
    assert [(r[0], r[1], r[2]) for r in rows] == [
        ("deep-house", "manual", 100),
        ("house", "manual", 100),
    ]


async def test_reclassify_requires_genre_ids(
    logged_in_client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    sid = await create_station(slug="pend", status="pending")
    resp = await logged_in_client.put(
        f"/api/v1/admin/stations/{sid}/curate",
        json={"decision": "reclassify", "genre_ids": []},
    )
    assert resp.status_code == 422


async def test_logs_to_curation_log(
    logged_in_client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
    db_session: AsyncSession,
) -> None:
    sid = await create_station(slug="pend", status="pending")
    resp = await logged_in_client.put(
        f"/api/v1/admin/stations/{sid}/curate",
        json={"decision": "approve", "notes": "clean sound"},
    )
    log_id = resp.json()["log_id"]
    row = (
        await db_session.execute(
            text(
                "SELECT admin_id, station_id, decision::text, notes "
                "FROM curation_log WHERE id = :id",
            ),
            {"id": log_id},
        )
    ).first()
    assert row is not None
    assert str(row[1]) == str(sid)
    assert row[2] == "approve"
    assert row[3] == "clean sound"


async def test_invalidates_genres_cache(
    logged_in_client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
    mocker: MockerFixture,
) -> None:
    sid = await create_station(slug="pend", status="pending", genre_slugs=["techno"])

    spy = mocker.spy(genres_service, "fetch_genres_with_counts")

    r1 = await logged_in_client.get("/api/v1/genres")
    assert r1.status_code == 200
    assert spy.call_count == 1

    r2 = await logged_in_client.get("/api/v1/genres")
    assert r2.status_code == 200
    assert spy.call_count == 1  # cached

    cur = await logged_in_client.put(
        f"/api/v1/admin/stations/{sid}/curate", json={"decision": "approve"},
    )
    assert cur.status_code == 200

    r3 = await logged_in_client.get("/api/v1/genres")
    assert r3.status_code == 200
    assert spy.call_count == 2  # cache invalidated


async def test_404_for_missing_station(logged_in_client: AsyncClient) -> None:
    resp = await logged_in_client.put(
        "/api/v1/admin/stations/00000000-0000-0000-0000-000000000000/curate",
        json={"decision": "approve"},
    )
    assert resp.status_code == 404
