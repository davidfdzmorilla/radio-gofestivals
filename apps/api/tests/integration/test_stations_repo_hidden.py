from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def _set_hidden(session: AsyncSession, slug: str, *, hidden: bool) -> None:
    await session.execute(
        text("UPDATE stations SET hidden = :h WHERE slug = :s"),
        {"h": hidden, "s": slug},
    )
    await session.commit()


async def test_list_active_excludes_hidden(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="visible", genre_slugs=["techno"])
    await create_station(slug="ocult", genre_slugs=["techno"])
    await _set_hidden(db_session, "ocult", hidden=True)

    r = await client.get("/api/v1/stations", params={"genre": "techno"})
    assert r.status_code == 200
    slugs = {i["slug"] for i in r.json()["items"]}
    assert slugs == {"visible"}


async def test_list_active_curated_excludes_hidden(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="cur-visible", curated=True, genre_slugs=["techno"])
    await create_station(slug="cur-hidden", curated=True, genre_slugs=["techno"])
    await _set_hidden(db_session, "cur-hidden", hidden=True)

    r = await client.get("/api/v1/stations", params={"curated": "true"})
    slugs = {i["slug"] for i in r.json()["items"]}
    assert "cur-visible" in slugs
    assert "cur-hidden" not in slugs


async def test_station_detail_still_accessible_when_hidden(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="hidden-but-accessible", genre_slugs=["techno"])
    await _set_hidden(db_session, "hidden-but-accessible", hidden=True)

    r = await client.get("/api/v1/stations/hidden-but-accessible")
    assert r.status_code == 200
    assert r.json()["slug"] == "hidden-but-accessible"


async def test_genres_count_excludes_hidden(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="t1", genre_slugs=["techno"])
    await create_station(slug="t2", genre_slugs=["techno"])
    await create_station(slug="t3", genre_slugs=["techno"])
    await _set_hidden(db_session, "t2", hidden=True)

    r = await client.get("/api/v1/genres")
    assert r.status_code == 200
    tree = r.json()
    techno = next((g for g in tree if g["slug"] == "techno"), None)
    assert techno is not None
    assert techno["station_count"] == 2
