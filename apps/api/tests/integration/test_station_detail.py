from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def test_detail_returns_data(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    station_id = await create_station(
        slug="detail-ok",
        name="Detail OK",
        genre_slugs=["techno", "minimal"],
    )
    await db_session.execute(
        text(
            """
            INSERT INTO now_playing (station_id, title, artist)
            VALUES (:sid, 'Track 1', 'Artist A'),
                   (:sid, 'Track 2', 'Artist B')
            """,
        ),
        {"sid": station_id},
    )
    await db_session.commit()

    r = await client.get("/api/v1/stations/detail-ok")
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "detail-ok"
    assert {g["slug"] for g in body["genres"]} == {"techno", "minimal"}
    assert len(body["now_playing"]) == 2


async def test_detail_404_for_non_active(client: AsyncClient, create_station) -> None:  # type: ignore[no-untyped-def]
    await create_station(slug="rota", status="broken")
    r = await client.get("/api/v1/stations/rota")
    assert r.status_code == 404


async def test_detail_404_for_missing(client: AsyncClient) -> None:
    r = await client.get("/api/v1/stations/no-such-station")
    assert r.status_code == 404
