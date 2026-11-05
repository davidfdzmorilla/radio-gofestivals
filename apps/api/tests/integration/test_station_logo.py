"""GET /stations/{slug}/logo y logo_hash en listados/detalle (ADR 011)."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

SM = b"RIFF\x10\x00\x00\x00WEBPsmall-logo-bytes"
LG = b"RIFF\x20\x00\x00\x00WEBPlarge-logo-bytes-longer"
HASH = "abc123def456"

CreateStation = Callable[..., Awaitable[uuid.UUID]]


async def _logo(
    db: AsyncSession,
    station_id: uuid.UUID,
    *,
    status: str = "ok",
    content_hash: str | None = HASH,
    with_data: bool = True,
    set_station_hash: bool = True,
) -> None:
    await db.execute(
        text(
            """
            INSERT INTO station_logos
                (station_id, source_url, status, content_hash, data_sm, data_lg)
            VALUES (:id, 'https://cdn.example/logo.png', :status, :hash, :sm, :lg)
            """,
        ),
        {
            "id": station_id,
            "status": status,
            "hash": content_hash,
            "sm": SM if with_data else None,
            "lg": LG if with_data else None,
        },
    )
    if set_station_hash and status == "ok":
        await db.execute(
            text("UPDATE stations SET logo_hash = :hash WHERE id = :id"),
            {"id": station_id, "hash": content_hash},
        )
    await db.commit()


# --- el endpoint -----------------------------------------------------------


async def test_serves_the_processed_webp_in_both_sizes(
    client: AsyncClient, create_station: CreateStation, db_session: AsyncSession
) -> None:
    await _logo(db_session, await create_station(slug="radio-a"))

    lg = await client.get("/api/v1/stations/radio-a/logo")
    assert lg.status_code == 200
    assert lg.headers["content-type"] == "image/webp"
    assert lg.content == LG  # por defecto, el grande

    sm = await client.get("/api/v1/stations/radio-a/logo?size=sm")
    assert sm.status_code == 200
    assert sm.content == SM
    assert lg.headers["x-content-type-options"] == "nosniff"


async def test_a_versioned_url_is_cached_for_a_year_as_immutable(
    client: AsyncClient, create_station: CreateStation, db_session: AsyncSession
) -> None:
    await _logo(db_session, await create_station(slug="radio-a"))
    resp = await client.get(f"/api/v1/stations/radio-a/logo?size=sm&v={HASH}")
    assert resp.headers["cache-control"] == "public, max-age=31536000, immutable"


@pytest.mark.parametrize("query", ["", "?v=", "?v=old", "?v=abc123def4567"])
async def test_an_unversioned_or_stale_url_is_only_cached_for_an_hour(
    client: AsyncClient, create_station: CreateStation, db_session: AsyncSession, query: str
) -> None:
    await _logo(db_session, await create_station(slug="radio-a"))
    resp = await client.get(f"/api/v1/stations/radio-a/logo{query}")
    assert resp.status_code == 200
    cache = resp.headers["cache-control"]
    assert "immutable" not in cache
    assert "max-age=3600" in cache


async def test_etag_gives_a_304_without_body(
    client: AsyncClient, create_station: CreateStation, db_session: AsyncSession
) -> None:
    await _logo(db_session, await create_station(slug="radio-a"))
    first = await client.get("/api/v1/stations/radio-a/logo?size=sm")
    etag = first.headers["etag"]
    assert etag == f'"{HASH}-sm"'

    again = await client.get(
        "/api/v1/stations/radio-a/logo?size=sm", headers={"If-None-Match": etag}
    )
    assert again.status_code == 304
    assert again.content == b""
    assert again.headers["etag"] == etag

    other_size = await client.get(
        "/api/v1/stations/radio-a/logo?size=lg", headers={"If-None-Match": etag}
    )
    assert other_size.status_code == 200  # el ETag del pequeño no vale para el grande


async def test_a_changed_logo_changes_the_etag(
    client: AsyncClient, create_station: CreateStation, db_session: AsyncSession
) -> None:
    sid = await create_station(slug="radio-a")
    await _logo(db_session, sid)
    old = (await client.get("/api/v1/stations/radio-a/logo")).headers["etag"]
    await db_session.execute(
        text("UPDATE station_logos SET content_hash = 'ffffffffffff' WHERE station_id = :id"),
        {"id": sid},
    )
    await db_session.commit()
    resp = await client.get("/api/v1/stations/radio-a/logo", headers={"If-None-Match": old})
    assert resp.status_code == 200
    assert resp.headers["etag"] != old


@pytest.mark.parametrize("size", ["xl", "SM", "0", "sm;lg"])
async def test_an_invalid_size_is_a_422(client: AsyncClient, size: str) -> None:
    assert (await client.get(f"/api/v1/stations/x/logo?size={size}")).status_code == 422


async def test_unknown_station_and_station_without_logo_are_404(
    client: AsyncClient, create_station: CreateStation
) -> None:
    await create_station(slug="no-logo")
    assert (await client.get("/api/v1/stations/nope/logo")).status_code == 404
    assert (await client.get("/api/v1/stations/no-logo/logo")).status_code == 404


@pytest.mark.parametrize("status", ["failed", "rejected"])
async def test_logos_that_are_not_ok_are_not_served(
    client: AsyncClient, create_station: CreateStation, db_session: AsyncSession, status: str
) -> None:
    await _logo(
        db_session, await create_station(slug="radio-a"), status=status, set_station_hash=False
    )
    assert (await client.get("/api/v1/stations/radio-a/logo")).status_code == 404


async def test_an_ok_row_without_image_data_is_404_not_a_500(
    client: AsyncClient, create_station: CreateStation, db_session: AsyncSession
) -> None:
    await _logo(
        db_session, await create_station(slug="radio-a"), with_data=False, content_hash=None
    )
    assert (await client.get("/api/v1/stations/radio-a/logo")).status_code == 404


@pytest.mark.parametrize("status", ["pending", "broken", "rejected", "inactive"])
async def test_stations_that_are_not_active_do_not_expose_a_logo(
    client: AsyncClient, create_station: CreateStation, db_session: AsyncSession, status: str
) -> None:
    await _logo(db_session, await create_station(slug="radio-a", status=status))
    assert (await client.get("/api/v1/stations/radio-a/logo")).status_code == 404


async def test_hidden_stations_do_not_expose_a_logo(
    client: AsyncClient, create_station: CreateStation, db_session: AsyncSession
) -> None:
    sid = await create_station(slug="radio-a")
    await _logo(db_session, sid)
    await db_session.execute(text("UPDATE stations SET hidden = true WHERE id = :id"), {"id": sid})
    await db_session.commit()
    assert (await client.get("/api/v1/stations/radio-a/logo")).status_code == 404


async def test_the_logo_route_does_not_shadow_the_station_detail(
    client: AsyncClient, create_station: CreateStation
) -> None:
    await create_station(slug="radio-a")
    assert (await client.get("/api/v1/stations/radio-a")).status_code == 200


# --- logo_hash en las respuestas -------------------------------------------


async def test_the_list_and_the_detail_expose_logo_hash(
    client: AsyncClient, create_station: CreateStation, db_session: AsyncSession
) -> None:
    await _logo(db_session, await create_station(slug="with-logo", quality_score=90))
    await create_station(slug="without-logo", quality_score=10)

    items = {i["slug"]: i for i in (await client.get("/api/v1/stations")).json()["items"]}
    assert items["with-logo"]["logo_hash"] == HASH
    assert items["without-logo"]["logo_hash"] is None

    assert (await client.get("/api/v1/stations/with-logo")).json()["logo_hash"] == HASH
    assert (await client.get("/api/v1/stations/without-logo")).json()["logo_hash"] is None


async def test_logo_bytes_never_leak_into_station_payloads(
    client: AsyncClient, create_station: CreateStation, db_session: AsyncSession
) -> None:
    await _logo(db_session, await create_station(slug="radio-a"))
    for path in ("/api/v1/stations", "/api/v1/stations/radio-a"):
        body = (await client.get(path)).text
        assert "large-logo-bytes" not in body
        assert "small-logo-bytes" not in body
        assert "data_lg" not in body
        assert "data_sm" not in body
