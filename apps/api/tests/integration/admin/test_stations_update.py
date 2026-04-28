from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

from tests.integration.admin.test_stations_list import _seed_station

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def test_401_without_auth(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    sid = await _seed_station(db_session, slug="u-anon")
    resp = await client.patch(
        f"/api/v1/admin/stations/{sid}", json={"curated": True},
    )
    assert resp.status_code == 401


async def test_toggle_curated_logs_audit(
    logged_in_client: AsyncClient, db_session: AsyncSession,
) -> None:
    sid = await _seed_station(db_session, slug="u-cur", curated=False)
    resp = await logged_in_client.patch(
        f"/api/v1/admin/stations/{sid}", json={"curated": True},
    )
    assert resp.status_code == 200
    assert resp.json()["curated"] is True

    decision = (
        await db_session.execute(
            text(
                "SELECT decision::text FROM curation_log "
                "WHERE station_id = :id ORDER BY created_at DESC LIMIT 1",
            ),
            {"id": str(sid)},
        )
    ).scalar_one()
    assert decision == "toggle_curated"


async def test_change_status_logs_audit(
    logged_in_client: AsyncClient, db_session: AsyncSession,
) -> None:
    sid = await _seed_station(db_session, slug="u-st", status="active")
    resp = await logged_in_client.patch(
        f"/api/v1/admin/stations/{sid}", json={"status": "inactive"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "inactive"

    decision = (
        await db_session.execute(
            text(
                "SELECT decision::text FROM curation_log "
                "WHERE station_id = :id ORDER BY created_at DESC LIMIT 1",
            ),
            {"id": str(sid)},
        )
    ).scalar_one()
    assert decision == "change_status"


async def test_edit_metadata_logs_audit(
    logged_in_client: AsyncClient, db_session: AsyncSession,
) -> None:
    sid = await _seed_station(db_session, slug="u-meta", name="Old")
    resp = await logged_in_client.patch(
        f"/api/v1/admin/stations/{sid}",
        json={"name": "New name"},
    )
    assert resp.status_code == 200

    decision = (
        await db_session.execute(
            text(
                "SELECT decision::text FROM curation_log "
                "WHERE station_id = :id ORDER BY created_at DESC LIMIT 1",
            ),
            {"id": str(sid)},
        )
    ).scalar_one()
    assert decision == "edit_metadata"


async def test_multiple_changes_log_one_entry_per_kind(
    logged_in_client: AsyncClient, db_session: AsyncSession,
) -> None:
    sid = await _seed_station(
        db_session, slug="u-multi", curated=False, status="active", name="A",
    )
    resp = await logged_in_client.patch(
        f"/api/v1/admin/stations/{sid}",
        json={"curated": True, "status": "inactive", "name": "B"},
    )
    assert resp.status_code == 200

    rows = (
        await db_session.execute(
            text(
                "SELECT decision::text FROM curation_log "
                "WHERE station_id = :id ORDER BY id",
            ),
            {"id": str(sid)},
        )
    ).all()
    decisions = {r[0] for r in rows}
    assert decisions == {"toggle_curated", "change_status", "edit_metadata"}
    assert len(rows) == 3


async def test_no_op_does_not_log(
    logged_in_client: AsyncClient, db_session: AsyncSession,
) -> None:
    sid = await _seed_station(db_session, slug="u-noop", curated=True)
    resp = await logged_in_client.patch(
        f"/api/v1/admin/stations/{sid}", json={"curated": True},
    )
    assert resp.status_code == 200

    count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM curation_log WHERE station_id = :id"),
            {"id": str(sid)},
        )
    ).scalar_one()
    assert int(count) == 0


async def test_status_pending_rejected(
    logged_in_client: AsyncClient, db_session: AsyncSession,
) -> None:
    sid = await _seed_station(db_session, slug="u-pending", status="active")
    resp = await logged_in_client.patch(
        f"/api/v1/admin/stations/{sid}", json={"status": "pending"},
    )
    assert resp.status_code == 422  # pydantic Literal mismatch


async def test_slug_conflict(
    logged_in_client: AsyncClient, db_session: AsyncSession,
) -> None:
    await _seed_station(db_session, slug="taken")
    sid = await _seed_station(db_session, slug="mine")
    resp = await logged_in_client.patch(
        f"/api/v1/admin/stations/{sid}", json={"slug": "taken"},
    )
    assert resp.status_code == 409


async def test_invalid_genre_ids(
    logged_in_client: AsyncClient, db_session: AsyncSession,
) -> None:
    sid = await _seed_station(db_session, slug="u-bad-genre")
    resp = await logged_in_client.patch(
        f"/api/v1/admin/stations/{sid}", json={"genre_ids": [99999]},
    )
    assert resp.status_code == 400


async def test_genre_ids_replace_set(
    logged_in_client: AsyncClient, db_session: AsyncSession,
) -> None:
    techno = int(
        (
            await db_session.execute(text("SELECT id FROM genres WHERE slug='techno'"))
        ).scalar_one(),
    )
    house = int(
        (
            await db_session.execute(text("SELECT id FROM genres WHERE slug='house'"))
        ).scalar_one(),
    )
    sid = await _seed_station(db_session, slug="u-genres", genre_ids=[techno])

    resp = await logged_in_client.patch(
        f"/api/v1/admin/stations/{sid}", json={"genre_ids": [house]},
    )
    assert resp.status_code == 200

    rows = (
        await db_session.execute(
            text(
                "SELECT g.slug FROM station_genres sg "
                "JOIN genres g ON g.id = sg.genre_id "
                "WHERE sg.station_id = :id",
            ),
            {"id": str(sid)},
        )
    ).all()
    assert {r[0] for r in rows} == {"house"}
