from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import text

from scripts.compute_station_similarity import run_compute

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def _genre_id(db_session: AsyncSession, slug: str) -> int:
    return int(
        (
            await db_session.execute(
                text("SELECT id FROM genres WHERE slug = :s"),
                {"s": slug},
            )
        ).scalar_one(),
    )


async def _insert_station(
    db_session: AsyncSession,
    *,
    slug: str,
    genre_slug: str,
    confidence: int = 100,
    quality: int = 80,
    country: str | None = "ES",
    language: str | None = "spanish",
    status: str = "active",
) -> uuid.UUID:
    sid = (
        await db_session.execute(
            text(
                """
                INSERT INTO stations
                    (slug, name, country_code, language, quality_score, status)
                VALUES (:slug, :slug, :cc, :lang, :q, CAST(:st AS station_status))
                RETURNING id
                """,
            ),
            {"slug": slug, "cc": country, "lang": language, "q": quality, "st": status},
        )
    ).scalar_one()
    gid = await _genre_id(db_session, genre_slug)
    await db_session.execute(
        text(
            """
            INSERT INTO station_genres (station_id, genre_id, source, confidence)
            VALUES (:sid, :gid, 'manual', :conf)
            """,
        ),
        {"sid": sid, "gid": gid, "conf": confidence},
    )
    await db_session.commit()
    return uuid.UUID(str(sid))


async def _insert_play(
    db_session: AsyncSession,
    station_id: uuid.UUID,
    client: uuid.UUID,
) -> None:
    await db_session.execute(
        text(
            """
            INSERT INTO station_plays (station_id, client_id)
            VALUES (:sid, :cid)
            """,
        ),
        {"sid": str(station_id), "cid": str(client)},
    )
    await db_session.commit()


async def _rows(db_session: AsyncSession) -> list[tuple]:
    return list(
        (
            await db_session.execute(
                text(
                    """
                    SELECT station_id, similar_station_id, score,
                           genre_score, coplay_score, rank
                    FROM station_similarity
                    ORDER BY station_id, rank
                    """,
                ),
            )
        ).all(),
    )


async def test_same_genre_stations_are_neighbors(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    a = await _insert_station(db_session, slug="sim-a", genre_slug="techno")
    b = await _insert_station(db_session, slug="sim-b", genre_slug="techno")
    await _insert_station(db_session, slug="sim-c", genre_slug="house")

    await run_compute(maker)

    rows = await _rows(db_session)
    pairs = {(str(r[0]), str(r[1])): float(r[2]) for r in rows}
    assert pairs[(str(a), str(b))] == pairs[(str(b), str(a))]
    # techno+techno (cos=1) + mismo idioma + mismo país = 0.50+0.15+0.10
    assert abs(pairs[(str(a), str(b))] - 0.75) < 0.01


async def test_low_quality_destination_excluded(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    good = await _insert_station(db_session, slug="q-good", genre_slug="techno")
    bad = await _insert_station(
        db_session,
        slug="q-bad",
        genre_slug="techno",
        quality=10,
    )

    await run_compute(maker)

    rows = await _rows(db_session)
    destinations = {str(r[1]) for r in rows}
    sources = {str(r[0]) for r in rows}
    assert str(bad) not in destinations  # gate quality >= 30
    assert str(bad) in sources  # pero sí recibe vecinos
    assert str(good) in destinations


async def test_coplay_boosts_score(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    a = await _insert_station(db_session, slug="cp-a", genre_slug="techno")
    b = await _insert_station(db_session, slug="cp-b", genre_slug="techno")
    c = await _insert_station(db_session, slug="cp-c", genre_slug="techno")
    # 3 oyentes comunes a<->b (umbral mínimo); c sin co-escucha
    for _ in range(3):
        ident = uuid.uuid4()
        await _insert_play(db_session, a, ident)
        await _insert_play(db_session, b, ident)

    await run_compute(maker)

    rows = await _rows(db_session)
    by_pair = {(str(r[0]), str(r[1])): r for r in rows}
    boosted = by_pair[(str(a), str(b))]
    plain = by_pair[(str(a), str(c))]
    assert float(boosted[4]) > 0  # coplay_score
    assert float(plain[4]) == 0
    assert float(boosted[2]) > float(plain[2])


async def test_ranks_are_ordered_and_consecutive(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    base = await _insert_station(db_session, slug="rk-base", genre_slug="techno")
    for i in range(4):
        await _insert_station(db_session, slug=f"rk-{i}", genre_slug="techno")

    await run_compute(maker)

    rows = [r for r in await _rows(db_session) if str(r[0]) == str(base)]
    ranks = [int(r[5]) for r in rows]
    scores = [float(r[2]) for r in rows]
    assert ranks == list(range(1, len(rows) + 1))
    assert scores == sorted(scores, reverse=True)


async def test_dry_run_writes_nothing(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    await _insert_station(db_session, slug="dr-a", genre_slug="techno")
    await _insert_station(db_session, slug="dr-b", genre_slug="techno")

    stats = await run_compute(maker, dry_run=True)

    assert stats["similarity_rows"] > 0
    assert await _rows(db_session) == []
