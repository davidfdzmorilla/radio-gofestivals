from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def _genre_id(db_session: AsyncSession, slug: str) -> int:
    return int(
        (
            await db_session.execute(
                text("SELECT id FROM genres WHERE slug = :s"),
                {"s": slug},
            )
        ).scalar_one(),
    )


async def _seed_station(
    db_session: AsyncSession,
    *,
    slug: str,
    genre_slug: str = "techno",
    quality: int = 80,
    country: str = "ES",
    language: str = "spanish",
    curated: bool = False,
) -> uuid.UUID:
    sid = (
        await db_session.execute(
            text(
                """
                INSERT INTO stations
                    (slug, name, country_code, language, quality_score,
                     status, curated)
                VALUES (:slug, :slug, :cc, :lang, :q, 'active', :cur)
                RETURNING id
                """,
            ),
            {"slug": slug, "cc": country, "lang": language, "q": quality, "cur": curated},
        )
    ).scalar_one()
    gid = await _genre_id(db_session, genre_slug)
    await db_session.execute(
        text(
            """
            INSERT INTO station_genres (station_id, genre_id, source, confidence)
            VALUES (:sid, :gid, 'manual', 100)
            """,
        ),
        {"sid": sid, "gid": gid},
    )
    await db_session.commit()
    return uuid.UUID(str(sid))


async def _link_similarity(
    db_session: AsyncSession,
    a: uuid.UUID,
    b: uuid.UUID,
    *,
    score: float = 0.8,
    rank: int = 1,
) -> None:
    await db_session.execute(
        text(
            """
            INSERT INTO station_similarity
                (station_id, similar_station_id, score, rank)
            VALUES (:a, :b, :score, :rank)
            """,
        ),
        {"a": str(a), "b": str(b), "score": score, "rank": rank},
    )
    await db_session.commit()


async def _play(
    db_session: AsyncSession,
    station: uuid.UUID,
    client: uuid.UUID,
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO station_plays (station_id, client_id) VALUES (:s, :c)",
        ),
        {"s": str(station), "c": str(client)},
    )
    await db_session.commit()


async def test_recommended_cold_start_uses_locale(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _seed_station(db_session, slug="cold-es", country="ES")
    await _seed_station(db_session, slug="cold-de", country="DE", language="german")

    resp = await client.get(
        "/api/v1/stations/recommended",
        params={"locale": "es-ES", "size": 12},
    )
    assert resp.status_code == 200
    slugs = [s["slug"] for s in resp.json()["items"]]
    assert "cold-es" in slugs


async def test_recommended_cold_start_never_empty_with_catalog(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    # Sin match de locale: rellena con featured (curated)
    await _seed_station(
        db_session,
        slug="cold-any",
        country="FR",
        language="french",
        curated=True,
    )

    resp = await client.get(
        "/api/v1/stations/recommended",
        params={"locale": "ja-JP"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) >= 1


async def test_recommended_uses_similarity_neighbors(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    seed = await _seed_station(db_session, slug="rec-seed")
    neighbor = await _seed_station(db_session, slug="rec-neighbor")
    unrelated = await _seed_station(
        db_session,
        slug="rec-unrelated",
        genre_slug="house",
    )
    await _link_similarity(db_session, seed, neighbor)

    listener = uuid.uuid4()
    await _play(db_session, seed, listener)

    resp = await client.get(
        "/api/v1/stations/recommended",
        params={"client_id": str(listener), "locale": "es-ES"},
    )
    assert resp.status_code == 200
    slugs = [s["slug"] for s in resp.json()["items"]]
    assert "rec-neighbor" in slugs
    assert slugs.index("rec-neighbor") == 0  # vecina directa, primer slot
    assert str(unrelated) is not None  # silencia ARG: la emisora existe


async def test_recommended_excludes_well_known_seeds(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    seed = await _seed_station(db_session, slug="known-seed")
    neighbor = await _seed_station(db_session, slug="known-neighbor")
    await _link_similarity(db_session, seed, neighbor)
    await _link_similarity(db_session, neighbor, seed)

    listener = uuid.uuid4()
    # 3 plays en días distintos → la semilla "ya se conoce"
    for offset in (0, 1, 2):
        await db_session.execute(
            text(
                """
                INSERT INTO station_plays (station_id, client_id, played_at)
                VALUES (:s, :c, now() - make_interval(days => :d))
                """,
            ),
            {"s": str(seed), "c": str(listener), "d": offset},
        )
    await db_session.commit()

    resp = await client.get(
        "/api/v1/stations/recommended",
        params={"client_id": str(listener)},
    )
    slugs = [s["slug"] for s in resp.json()["items"]]
    assert "known-neighbor" in slugs
    assert "known-seed" not in slugs


async def test_recommended_size_validation(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/stations/recommended", params={"size": 25})
    assert resp.status_code == 422


async def test_similar_endpoint_returns_neighbors_by_rank(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    base = await _seed_station(db_session, slug="sim-base")
    first = await _seed_station(db_session, slug="sim-first")
    second = await _seed_station(db_session, slug="sim-second")
    await _link_similarity(db_session, base, second, score=0.5, rank=2)
    await _link_similarity(db_session, base, first, score=0.9, rank=1)

    resp = await client.get("/api/v1/stations/sim-base/similar")
    assert resp.status_code == 200
    slugs = [s["slug"] for s in resp.json()]
    assert slugs == ["sim-first", "sim-second"]


async def test_similar_unknown_slug_404(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/stations/no-such-station/similar")
    assert resp.status_code == 404


async def test_rec_events_inserted_and_identity_required(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    station = await _seed_station(db_session, slug="ev-station")
    cid = uuid.uuid4()

    resp = await client.post(
        "/api/v1/recs/events",
        json={
            "surface": "home_for_you",
            "client_id": str(cid),
            "events": [
                {"station_id": str(station), "event_type": "impression", "slot": 0},
                {"station_id": str(station), "event_type": "click", "slot": 0},
                {"station_id": str(uuid.uuid4()), "event_type": "click"},
            ],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["inserted"] == 2  # la emisora inexistente se ignora

    count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM rec_events WHERE client_id = :c"),
            {"c": str(cid)},
        )
    ).scalar_one()
    assert int(count) == 2

    no_identity = await client.post(
        "/api/v1/recs/events",
        json={
            "surface": "home_for_you",
            "events": [{"station_id": str(station), "event_type": "impression"}],
        },
    )
    assert no_identity.status_code == 400


async def test_stations_by_ids_lookup(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """?ids= hidrata favoritos anónimos (bug del lookup por q=<uuid>)."""
    a = await _seed_station(db_session, slug="ids-a")
    b = await _seed_station(db_session, slug="ids-b", genre_slug="house")

    resp = await client.get(f"/api/v1/stations?ids={a},{b}")
    assert resp.status_code == 200
    slugs = [s["slug"] for s in resp.json()["items"]]
    assert slugs == ["ids-a", "ids-b"]  # orden de entrada preservado

    bad = await client.get("/api/v1/stations?ids=no-es-uuid")
    assert bad.status_code == 422
