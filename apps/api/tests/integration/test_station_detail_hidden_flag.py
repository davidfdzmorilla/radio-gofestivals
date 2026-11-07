"""El detalle expone `hidden` para que la web pueda marcar noindex (ADR 012)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def test_detail_reports_hidden_false_for_a_visible_station(
    client: AsyncClient,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="visible-one", genre_slugs=["techno"])
    resp = await client.get("/api/v1/stations/visible-one")
    assert resp.status_code == 200
    assert resp.json()["hidden"] is False


async def test_detail_of_a_hidden_station_stays_reachable_and_reports_hidden_true(
    client: AsyncClient,
    db_session: AsyncSession,
    create_station,  # type: ignore[no-untyped-def]
) -> None:
    await create_station(slug="hidden-one", genre_slugs=["techno"])
    await db_session.execute(
        text(
            "UPDATE stations SET hidden = true, hidden_by = 'classifier' WHERE slug = 'hidden-one'"
        ),
    )
    await db_session.commit()

    resp = await client.get("/api/v1/stations/hidden-one")
    assert resp.status_code == 200
    assert resp.json()["hidden"] is True
