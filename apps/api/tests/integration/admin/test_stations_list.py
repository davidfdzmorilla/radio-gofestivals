from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def _seed_station(
    db: AsyncSession,
    *,
    slug: str,
    name: str | None = None,
    status: str = "active",
    curated: bool = False,
    country_code: str | None = "ES",
    quality_score: int = 70,
    primary_stream_url: str | None = "https://example.com/p.mp3",
    primary_codec: str = "mp3",
    primary_bitrate: int | None = 128,
    extra_streams: int = 0,
    genre_ids: list[int] | None = None,
) -> uuid.UUID:
    sid = uuid.UUID(
        str(
            (
                await db.execute(
                    text(
                        """
                        INSERT INTO stations
                            (slug, name, status, curated, country_code,
                             quality_score)
                        VALUES (:slug, :name, CAST(:st AS station_status),
                                :curated, :cc, :q)
                        RETURNING id
                        """,
                    ),
                    {
                        "slug": slug,
                        "name": name or slug.replace("-", " ").title(),
                        "st": status,
                        "curated": curated,
                        "cc": country_code,
                        "q": quality_score,
                    },
                )
            ).scalar_one(),
        ),
    )
    if primary_stream_url is not None:
        await db.execute(
            text(
                """
                INSERT INTO station_streams
                    (station_id, stream_url, codec, bitrate, is_primary, status)
                VALUES (:sid, :url, :codec, :br, true,
                        CAST('active' AS stream_status))
                """,
            ),
            {
                "sid": str(sid),
                "url": primary_stream_url,
                "codec": primary_codec,
                "br": primary_bitrate,
            },
        )
    for i in range(extra_streams):
        await db.execute(
            text(
                """
                INSERT INTO station_streams
                    (station_id, stream_url, codec, bitrate, is_primary, status)
                VALUES (:sid, :url, 'mp3', :br, false,
                        CAST('active' AS stream_status))
                """,
            ),
            {
                "sid": str(sid),
                "url": f"https://example.com/{slug}-{i}.mp3",
                "br": 64 + i * 32,
            },
        )
    for gid in genre_ids or []:
        await db.execute(
            text(
                """
                INSERT INTO station_genres (station_id, genre_id, source, confidence)
                VALUES (:sid, :gid, 'manual', 100)
                """,
            ),
            {"sid": str(sid), "gid": gid},
        )
    await db.commit()
    return sid


async def test_401_without_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/admin/stations")
    assert resp.status_code == 401


async def test_lists_all_paginated(
    logged_in_client: AsyncClient, db_session: AsyncSession,
) -> None:
    await _seed_station(db_session, slug="a", status="active")
    await _seed_station(db_session, slug="b", status="active")
    await _seed_station(db_session, slug="c", status="inactive")

    resp = await logged_in_client.get("/api/v1/admin/stations")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert {item["slug"] for item in body["items"]} == {"a", "b", "c"}


async def test_filter_by_status(
    logged_in_client: AsyncClient, db_session: AsyncSession,
) -> None:
    await _seed_station(db_session, slug="act-1", status="active")
    await _seed_station(db_session, slug="bro-1", status="broken")
    await _seed_station(db_session, slug="bro-2", status="broken")

    resp = await logged_in_client.get(
        "/api/v1/admin/stations", params={"status": "broken"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert all(it["status"] == "broken" for it in body["items"])


async def test_filter_by_curated(
    logged_in_client: AsyncClient, db_session: AsyncSession,
) -> None:
    await _seed_station(db_session, slug="cur-1", curated=True)
    await _seed_station(db_session, slug="cur-2", curated=True)
    await _seed_station(db_session, slug="not-cur", curated=False)

    resp = await logged_in_client.get(
        "/api/v1/admin/stations", params={"curated": "true"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert all(it["curated"] is True for it in body["items"])


async def test_search_matches_name_or_slug(
    logged_in_client: AsyncClient, db_session: AsyncSession,
) -> None:
    await _seed_station(db_session, slug="yammat-fm", name="Yammat FM")
    await _seed_station(db_session, slug="other", name="Different")

    by_name = await logged_in_client.get(
        "/api/v1/admin/stations", params={"search": "yammat"},
    )
    assert by_name.status_code == 200
    assert {it["slug"] for it in by_name.json()["items"]} == {"yammat-fm"}

    by_slug = await logged_in_client.get(
        "/api/v1/admin/stations", params={"search": "OTHE"},  # ILIKE
    )
    assert {it["slug"] for it in by_slug.json()["items"]} == {"other"}


async def test_pagination(
    logged_in_client: AsyncClient, db_session: AsyncSession,
) -> None:
    for i in range(5):
        await _seed_station(db_session, slug=f"p-{i}")

    resp = await logged_in_client.get(
        "/api/v1/admin/stations", params={"page": 2, "size": 2},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5
    assert body["page"] == 2
    assert body["size"] == 2
    assert body["pages"] == 3
    assert len(body["items"]) == 2


async def test_includes_primary_stream_and_counts(
    logged_in_client: AsyncClient, db_session: AsyncSession,
) -> None:
    techno = (
        await db_session.execute(text("SELECT id FROM genres WHERE slug='techno'"))
    ).scalar_one()
    await _seed_station(
        db_session,
        slug="full",
        primary_stream_url="https://example.com/main.mp3",
        primary_codec="mp3",
        primary_bitrate=192,
        extra_streams=2,
        genre_ids=[int(techno)],
    )

    resp = await logged_in_client.get(
        "/api/v1/admin/stations", params={"search": "full"},
    )
    body = resp.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["primary_stream"] is not None
    assert item["primary_stream"]["bitrate"] == 192
    assert item["stream_count"] == 3
    assert item["genre_count"] == 1
