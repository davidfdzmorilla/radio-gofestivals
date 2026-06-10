from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def test_country_facets_counts_active_visible_only(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="de-1", country_code="DE", genre_slugs=["techno"])
    await create_station(slug="de-2", country_code="DE", genre_slugs=["house"])
    await create_station(slug="es-1", country_code="ES", genre_slugs=["techno"])
    await create_station(slug="es-broken", country_code="ES", status="broken")
    await create_station(slug="es-hidden", country_code="ES")
    await create_station(slug="no-country", country_code=None)
    await db_session.execute(
        text("UPDATE stations SET hidden = true WHERE slug = 'es-hidden'"),
    )
    await db_session.commit()

    r = await client.get("/api/v1/stations/facets/countries")
    assert r.status_code == 200
    facets = r.json()
    # Orden: count desc, code asc. Sin NULL, sin broken, sin hidden.
    assert facets == [
        {"code": "DE", "station_count": 2},
        {"code": "ES", "station_count": 1},
    ]


async def test_country_facets_filters_by_genre(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="de-techno", country_code="DE", genre_slugs=["techno"])
    await create_station(slug="de-house", country_code="DE", genre_slugs=["house"])
    await create_station(slug="fr-techno", country_code="FR", genre_slugs=["techno"])

    r = await client.get(
        "/api/v1/stations/facets/countries",
        params={"genre": "techno"},
    )
    assert r.status_code == 200
    assert r.json() == [
        {"code": "DE", "station_count": 1},
        {"code": "FR", "station_count": 1},
    ]


async def test_trending_orders_by_click_trend_and_excludes_no_signal(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="rising", quality_score=50, genre_slugs=["techno"])
    await create_station(slug="steady", quality_score=99, genre_slugs=["techno"])
    await create_station(slug="hot", quality_score=60, genre_slugs=["house"])
    await db_session.execute(
        text(
            "UPDATE stations SET click_trend = CASE slug "
            "WHEN 'rising' THEN 0.5 WHEN 'hot' THEN 1.2 ELSE 0 END",
        ),
    )
    await db_session.commit()

    r = await client.get("/api/v1/stations/trending")
    assert r.status_code == 200
    slugs = [i["slug"] for i in r.json()["items"]]
    # 'steady' tiene el mejor quality_score pero click_trend 0 → fuera.
    assert slugs == ["hot", "rising"]


async def test_trending_filters_by_genre_and_caps_limit(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="t-1", genre_slugs=["techno"])
    await create_station(slug="h-1", genre_slugs=["house"])
    await db_session.execute(text("UPDATE stations SET click_trend = 1.0"))
    await db_session.commit()

    r = await client.get("/api/v1/stations/trending", params={"genre": "house"})
    assert [i["slug"] for i in r.json()["items"]] == ["h-1"]

    r = await client.get("/api/v1/stations/trending", params={"limit": 51})
    assert r.status_code == 422


async def test_new_orders_by_created_at_desc(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="old", genre_slugs=["techno"])
    await create_station(slug="newer", genre_slugs=["techno"])
    await create_station(slug="newest", genre_slugs=["techno"])
    # created_at explícito: los inserts del fixture pueden compartir timestamp.
    await db_session.execute(
        text(
            "UPDATE stations SET created_at = now() - CASE slug "
            "WHEN 'old' THEN interval '3 days' "
            "WHEN 'newer' THEN interval '2 days' "
            "ELSE interval '1 day' END",
        ),
    )
    await db_session.commit()

    r = await client.get("/api/v1/stations/new", params={"limit": 2})
    assert r.status_code == 200
    assert [i["slug"] for i in r.json()["items"]] == ["newest", "newer"]


async def test_new_excludes_inactive(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="ok", genre_slugs=["techno"])
    await create_station(slug="broken", status="broken", genre_slugs=["techno"])

    r = await client.get("/api/v1/stations/new")
    slugs = [i["slug"] for i in r.json()["items"]]
    assert slugs == ["ok"]
