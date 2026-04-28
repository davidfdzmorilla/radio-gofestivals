from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

from tests.integration.admin.test_stations_list import _seed_station

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def test_404_for_missing_station(logged_in_client: AsyncClient) -> None:
    resp = await logged_in_client.get(
        "/api/v1/admin/stations/00000000-0000-0000-0000-000000000000",
    )
    assert resp.status_code == 404


async def test_detail_returns_streams_and_genres(
    logged_in_client: AsyncClient, db_session: AsyncSession,
) -> None:
    techno = (
        await db_session.execute(text("SELECT id FROM genres WHERE slug='techno'"))
    ).scalar_one()
    sid = await _seed_station(
        db_session,
        slug="det-1",
        extra_streams=2,
        genre_ids=[int(techno)],
    )

    resp = await logged_in_client.get(f"/api/v1/admin/stations/{sid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["slug"] == "det-1"
    assert len(body["streams"]) == 3
    assert sum(1 for s in body["streams"] if s["is_primary"]) == 1
    assert len(body["genres"]) == 1
    assert body["genres"][0]["slug"] == "techno"
    assert body["audit"] == []


async def test_detail_includes_audit_history(
    logged_in_client: AsyncClient, db_session: AsyncSession,
) -> None:
    sid = await _seed_station(db_session, slug="det-audit", curated=False)
    # PATCH twice so two audit entries exist
    r1 = await logged_in_client.patch(
        f"/api/v1/admin/stations/{sid}",
        json={"curated": True, "notes": "first"},
    )
    assert r1.status_code == 200
    r2 = await logged_in_client.patch(
        f"/api/v1/admin/stations/{sid}",
        json={"curated": False, "notes": "second"},
    )
    assert r2.status_code == 200

    detail = (await logged_in_client.get(f"/api/v1/admin/stations/{sid}")).json()
    decisions = [a["decision"] for a in detail["audit"]]
    assert decisions.count("toggle_curated") == 2
