from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def test_401_without_auth(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/admin/operations/run",
        json={"command": "snapshot_clickcounts"},
    )
    assert resp.status_code == 401


async def test_catalog_returns_six_commands(
    logged_in_client: AsyncClient,
) -> None:
    resp = await logged_in_client.get("/api/v1/admin/operations/catalog")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 6
    keys = {entry["command"] for entry in body}
    assert "rb_sync_run" in keys
    assert "auto_curate" in keys


async def test_run_no_param_command_creates_pending_job(
    logged_in_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    resp = await logged_in_client.post(
        "/api/v1/admin/operations/run",
        json={"command": "snapshot_clickcounts"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["command"] == "snapshot_clickcounts"
    assert body["params_json"] in (None, {})
    assert body["admin_email"] == "admin@test.com"

    job_id = body["id"]
    row = (
        await db_session.execute(
            text(
                "SELECT command, status FROM admin_jobs WHERE id = :id",
            ),
            {"id": job_id},
        )
    ).first()
    assert row is not None
    assert row[0] == "snapshot_clickcounts"
    assert row[1] == "pending"


async def test_run_unknown_command_400(
    logged_in_client: AsyncClient,
) -> None:
    resp = await logged_in_client.post(
        "/api/v1/admin/operations/run",
        json={"command": "rm_rf_root"},
    )
    assert resp.status_code == 400
    assert "command_not_allowed" in resp.json()["detail"]


async def test_run_auto_curate_missing_admin_email_422(
    logged_in_client: AsyncClient,
) -> None:
    resp = await logged_in_client.post(
        "/api/v1/admin/operations/run",
        json={
            "command": "auto_curate",
            "params": {"min_quality": 70, "limit": 10},
        },
    )
    assert resp.status_code == 422
    assert "invalid_params" in resp.json()["detail"]


async def test_run_auto_curate_with_valid_params(
    logged_in_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    resp = await logged_in_client.post(
        "/api/v1/admin/operations/run",
        json={
            "command": "auto_curate",
            "params": {
                "admin_email": "davidfdzmorilla@gmail.com",
                "min_quality": 70,
                "limit": 10,
                "dry_run": True,
            },
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending"
    assert body["params_json"]["admin_email"] == "davidfdzmorilla@gmail.com"
    assert body["params_json"]["dry_run"] is True

    persisted = (
        await db_session.execute(
            text(
                "SELECT params_json FROM admin_jobs WHERE id = :id",
            ),
            {"id": body["id"]},
        )
    ).scalar_one()
    assert persisted["limit"] == 10


async def test_list_jobs_filter_by_status(
    logged_in_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Seed: enqueue two pending jobs, mark one as success.
    r1 = await logged_in_client.post(
        "/api/v1/admin/operations/run",
        json={"command": "snapshot_clickcounts"},
    )
    r2 = await logged_in_client.post(
        "/api/v1/admin/operations/run",
        json={"command": "compute_click_trends"},
    )
    job1 = r1.json()["id"]
    await db_session.execute(
        text(
            "UPDATE admin_jobs SET status = 'success', "
            "started_at = now(), finished_at = now() WHERE id = :id",
        ),
        {"id": job1},
    )
    await db_session.commit()
    _ = r2

    pending = await logged_in_client.get(
        "/api/v1/admin/operations/jobs", params={"status": "pending"},
    )
    assert pending.status_code == 200
    items = pending.json()["items"]
    assert all(it["status"] == "pending" for it in items)

    succ = await logged_in_client.get(
        "/api/v1/admin/operations/jobs", params={"status": "success"},
    )
    succ_items = succ.json()["items"]
    assert all(it["status"] == "success" for it in succ_items)


async def test_get_job_404(logged_in_client: AsyncClient) -> None:
    resp = await logged_in_client.get(
        "/api/v1/admin/operations/jobs/9999999",
    )
    assert resp.status_code == 404
