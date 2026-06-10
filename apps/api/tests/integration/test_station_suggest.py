from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def test_suggest_fuzzy_typo(client: AsyncClient, create_station) -> None:  # type: ignore[no-untyped-def]
    await create_station(slug="radio-underground", name="Radio Underground")
    await create_station(slug="big-fm", name="Big FM")

    r = await client.get("/api/v1/stations/suggest", params={"q": "undergrund"})
    assert r.status_code == 200
    slugs = [i["slug"] for i in r.json()]
    assert "radio-underground" in slugs
    assert "big-fm" not in slugs


async def test_suggest_short_prefix_two_chars(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    # El operador % de pg_trgm no matchea prefijos de 2 chars; el endpoint
    # debe encontrarlos por ILIKE y ordenarlos por quality_score (el boost
    # de prefijo empata a 0.85).
    await create_station(slug="techno-beats", name="Techno Beats", quality_score=90)
    await create_station(slug="techno-hub", name="Techno Hub", quality_score=50)
    await create_station(slug="trance-wave", name="Trance Wave")

    r = await client.get("/api/v1/stations/suggest", params={"q": "te"})
    assert r.status_code == 200
    slugs = [i["slug"] for i in r.json()]
    assert slugs.index("techno-beats") < slugs.index("techno-hub")
    assert "trance-wave" not in slugs


async def test_suggest_infix_match(client: AsyncClient, create_station) -> None:  # type: ignore[no-untyped-def]
    await create_station(slug="big-fm", name="Big FM")
    await create_station(slug="techno-hub", name="Techno Hub")

    r = await client.get("/api/v1/stations/suggest", params={"q": "fm"})
    assert r.status_code == 200
    slugs = [i["slug"] for i in r.json()]
    assert "big-fm" in slugs
    assert "techno-hub" not in slugs


async def test_suggest_limit_validation(client: AsyncClient, create_station) -> None:  # type: ignore[no-untyped-def]
    for i in range(3):
        await create_station(slug=f"techno-{i}", name=f"Techno {i}")

    r = await client.get("/api/v1/stations/suggest", params={"q": "techno", "limit": 50})
    assert r.status_code == 422

    r = await client.get("/api/v1/stations/suggest", params={"q": "techno", "limit": 1})
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_suggest_q_validation(client: AsyncClient) -> None:
    r = await client.get("/api/v1/stations/suggest")
    assert r.status_code == 422

    r = await client.get("/api/v1/stations/suggest", params={"q": ""})
    assert r.status_code == 422

    # Solo espacios pasa la validación de longitud pero normaliza a vacío.
    r = await client.get("/api/v1/stations/suggest", params={"q": "   "})
    assert r.status_code == 200
    assert r.json() == []


async def test_suggest_cache_hit(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
    db_session: AsyncSession,
) -> None:
    await create_station(slug="techno-beats", name="Techno Beats")

    r1 = await client.get("/api/v1/stations/suggest", params={"q": "techno"})
    assert [i["name"] for i in r1.json()] == ["Techno Beats"]

    await db_session.execute(
        text("UPDATE stations SET name = 'Renamed' WHERE slug = 'techno-beats'"),
    )
    await db_session.commit()

    # Segunda llamada (misma query normalizada): sirve el snapshot de Redis.
    r2 = await client.get("/api/v1/stations/suggest", params={"q": "  Techno "})
    assert [i["name"] for i in r2.json()] == ["Techno Beats"]


async def test_suggest_excludes_hidden_and_inactive(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
    db_session: AsyncSession,
) -> None:
    await create_station(slug="techno-live", name="Techno Live", status="active")
    await create_station(slug="techno-broken", name="Techno Broken", status="broken")
    await create_station(slug="techno-hidden", name="Techno Hidden", status="active")
    await db_session.execute(
        text("UPDATE stations SET hidden = true WHERE slug = 'techno-hidden'"),
    )
    await db_session.commit()

    r = await client.get("/api/v1/stations/suggest", params={"q": "techno"})
    slugs = {i["slug"] for i in r.json()}
    assert slugs == {"techno-live"}


async def test_suggest_payload_shape(client: AsyncClient, create_station) -> None:  # type: ignore[no-untyped-def]
    await create_station(slug="techno-beats", name="Techno Beats", genre_slugs=["techno"])

    r = await client.get("/api/v1/stations/suggest", params={"q": "techno"})
    items = r.json()
    assert len(items) == 1
    assert set(items[0].keys()) == {"slug", "name", "country_code", "genres"}
    assert items[0]["genres"] == ["techno"]


async def test_suggest_not_captured_by_slug_route(client: AsyncClient) -> None:
    # Protege el orden de declaración de rutas: /suggest debe resolverse
    # como endpoint propio, no como station_detail(slug="suggest") → 404.
    r = await client.get("/api/v1/stations/suggest", params={"q": "zz"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_suggest_like_wildcards_escaped(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="techno-beats", name="Techno Beats")

    # "%" no debe actuar como comodín ILIKE y matchear todo el catálogo.
    r = await client.get("/api/v1/stations/suggest", params={"q": "%"})
    assert r.status_code == 200
    assert r.json() == []
