from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

from tests.integration.admin.test_stations_list import _seed_station

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def test_401_without_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/admin/dashboard/stats")
    assert resp.status_code == 401


async def test_returns_full_shape_with_empty_db(
    logged_in_client: AsyncClient,
) -> None:
    resp = await logged_in_client.get("/api/v1/admin/dashboard/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {
        "kpis",
        "quality_distribution",
        "top_genres_curated",
        "top_countries",
        "recent_activity",
    }
    kpis = body["kpis"]
    assert kpis["stations_active"] == 0
    assert kpis["stations_curated"] == 0
    assert kpis["stations_broken"] == 0
    assert kpis["avg_quality_active"] == 0
    assert isinstance(body["quality_distribution"], list)
    assert isinstance(body["top_genres_curated"], list)
    assert isinstance(body["top_countries"], list)
    assert isinstance(body["recent_activity"], list)


async def test_kpis_with_seeded_data(
    logged_in_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _seed_station(
        db_session, slug="a", status="active", curated=True, quality_score=80,
    )
    await _seed_station(
        db_session, slug="b", status="active", curated=False, quality_score=40,
    )
    await _seed_station(
        db_session, slug="c", status="broken", curated=False, quality_score=10,
    )

    resp = await logged_in_client.get("/api/v1/admin/dashboard/stats")
    body = resp.json()

    kpis = body["kpis"]
    assert kpis["stations_active"] == 2
    assert kpis["stations_curated"] == 1
    assert kpis["stations_broken"] == 1
    # Avg quality only over active: (80 + 40) / 2 = 60.0
    assert kpis["avg_quality_active"] == 60.0
    # The math contract: curated is a subset of active.
    assert kpis["stations_active"] >= kpis["stations_curated"]


async def test_quality_distribution_buckets(
    logged_in_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Two in 70-89, one in 30-49
    await _seed_station(
        db_session, slug="hi-1", status="active", quality_score=80,
    )
    await _seed_station(
        db_session, slug="hi-2", status="active", quality_score=85,
    )
    await _seed_station(
        db_session, slug="mid", status="active", quality_score=45,
    )

    body = (
        await logged_in_client.get("/api/v1/admin/dashboard/stats")
    ).json()
    buckets = {
        b["bucket"]: b["count"] for b in body["quality_distribution"]
    }
    assert buckets.get("70-89") == 2
    assert buckets.get("30-49") == 1


async def test_top_countries_only_active(
    logged_in_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _seed_station(
        db_session, slug="es-1", status="active", country_code="ES",
    )
    await _seed_station(
        db_session, slug="es-2", status="active", country_code="ES",
    )
    await _seed_station(
        db_session, slug="fr-1", status="active", country_code="FR",
    )
    await _seed_station(
        db_session, slug="br-1", status="broken", country_code="DE",
    )

    body = (
        await logged_in_client.get("/api/v1/admin/dashboard/stats")
    ).json()
    countries = {
        c["country_code"]: c["count"] for c in body["top_countries"]
    }
    assert countries.get("ES") == 2
    assert countries.get("FR") == 1
    assert "DE" not in countries  # broken stations excluded


async def test_top_genres_curated_only(
    logged_in_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    techno = int(
        (
            await db_session.execute(
                text("SELECT id FROM genres WHERE slug = 'techno'"),
            )
        ).scalar_one(),
    )
    house = int(
        (
            await db_session.execute(
                text("SELECT id FROM genres WHERE slug = 'house'"),
            )
        ).scalar_one(),
    )
    # 2 curated active stations with techno
    await _seed_station(
        db_session,
        slug="cur-techno-1",
        status="active",
        curated=True,
        genre_ids=[techno],
    )
    await _seed_station(
        db_session,
        slug="cur-techno-2",
        status="active",
        curated=True,
        genre_ids=[techno, house],
    )
    # not curated → must NOT count for genres
    await _seed_station(
        db_session,
        slug="not-cur",
        status="active",
        curated=False,
        genre_ids=[techno],
    )

    body = (
        await logged_in_client.get("/api/v1/admin/dashboard/stats")
    ).json()
    by_genre = {
        g["name"]: g["count"] for g in body["top_genres_curated"]
    }
    assert by_genre.get("Techno") == 2
    assert by_genre.get("House") == 1


async def test_recent_activity_returns_curation_log(
    logged_in_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    sid = await _seed_station(db_session, slug="act-1", curated=False)
    # Trigger an admin action so curation_log gets one row
    resp = await logged_in_client.patch(
        f"/api/v1/admin/stations/{sid}", json={"curated": True},
    )
    assert resp.status_code == 200

    body = (
        await logged_in_client.get("/api/v1/admin/dashboard/stats")
    ).json()
    activity = body["recent_activity"]
    assert len(activity) >= 1
    first = activity[0]
    assert first["decision"] == "toggle_curated"
    assert first["station_slug"] == "act-1"
    assert first["admin_email"] == "admin@test.com"
