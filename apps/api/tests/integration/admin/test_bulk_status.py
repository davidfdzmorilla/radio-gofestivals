from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import text

from tests.integration.admin.test_stations_list import _seed_station

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def test_401_without_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/admin/stations/bulk-status-change",
        json={
            "station_ids": ["00000000-0000-0000-0000-000000000001"],
            "new_status": "inactive",
        },
    )
    assert resp.status_code == 401


async def test_422_when_empty_ids(logged_in_client: AsyncClient) -> None:
    resp = await logged_in_client.post(
        "/api/v1/admin/stations/bulk-status-change",
        json={"station_ids": [], "new_status": "inactive"},
    )
    assert resp.status_code == 422


async def test_422_when_too_many_ids(logged_in_client: AsyncClient) -> None:
    ids = [str(uuid.uuid4()) for _ in range(101)]
    resp = await logged_in_client.post(
        "/api/v1/admin/stations/bulk-status-change",
        json={"station_ids": ids, "new_status": "inactive"},
    )
    assert resp.status_code == 422


async def test_422_when_status_not_inactive(
    logged_in_client: AsyncClient,
) -> None:
    resp = await logged_in_client.post(
        "/api/v1/admin/stations/bulk-status-change",
        json={
            "station_ids": ["00000000-0000-0000-0000-000000000001"],
            "new_status": "active",
        },
    )
    assert resp.status_code == 422


async def test_bulk_inactivates_and_audits(
    logged_in_client: AsyncClient, db_session: AsyncSession,
) -> None:
    sid_a = await _seed_station(db_session, slug="b-a", status="broken")
    sid_b = await _seed_station(db_session, slug="b-b", status="broken")
    sid_c = await _seed_station(db_session, slug="b-c", status="active")

    resp = await logged_in_client.post(
        "/api/v1/admin/stations/bulk-status-change",
        json={
            "station_ids": [str(sid_a), str(sid_b), str(sid_c)],
            "new_status": "inactive",
            "reason": "cleanup chronic broken",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["affected"] == 3
    assert body["skipped"] == 0
    assert set(body["station_ids_affected"]) == {
        str(sid_a),
        str(sid_b),
        str(sid_c),
    }

    statuses = dict(
        (
            await db_session.execute(
                text(
                    "SELECT id::text, status::text FROM stations "
                    "WHERE id = ANY(CAST(:ids AS uuid[]))",
                ),
                {"ids": [str(sid_a), str(sid_b), str(sid_c)]},
            )
        ).all(),
    )
    assert statuses == {
        str(sid_a): "inactive",
        str(sid_b): "inactive",
        str(sid_c): "inactive",
    }

    audit_rows = (
        await db_session.execute(
            text(
                "SELECT decision::text, notes FROM curation_log "
                "WHERE station_id = ANY(CAST(:ids AS uuid[]))",
            ),
            {"ids": [str(sid_a), str(sid_b), str(sid_c)]},
        )
    ).all()
    assert len(audit_rows) == 3
    for decision, notes in audit_rows:
        assert decision == "change_status"
        assert notes.startswith("bulk_inactive:3_stations")
        assert "cleanup chronic broken" in notes


async def test_bulk_skips_already_inactive(
    logged_in_client: AsyncClient, db_session: AsyncSession,
) -> None:
    a = await _seed_station(db_session, slug="sk-a", status="inactive")
    b = await _seed_station(db_session, slug="sk-b", status="active")

    resp = await logged_in_client.post(
        "/api/v1/admin/stations/bulk-status-change",
        json={
            "station_ids": [str(a), str(b)],
            "new_status": "inactive",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["affected"] == 1
    assert body["skipped"] == 1
    assert body["station_ids_affected"] == [str(b)]


async def test_bulk_zero_affected_when_all_already_inactive(
    logged_in_client: AsyncClient, db_session: AsyncSession,
) -> None:
    a = await _seed_station(db_session, slug="z-a", status="inactive")
    resp = await logged_in_client.post(
        "/api/v1/admin/stations/bulk-status-change",
        json={"station_ids": [str(a)], "new_status": "inactive"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["affected"] == 0
    assert body["skipped"] == 1
    assert body["station_ids_affected"] == []
