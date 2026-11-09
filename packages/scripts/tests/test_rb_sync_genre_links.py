"""replace_rb_tag_links toca solo la diferencia (si no, mueve stations.updated_at cada noche)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import text

from scripts.rb_sync import SyncStats, replace_rb_tag_links

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

OLD = datetime(2026, 1, 1, tzinfo=UTC)


async def _station(db: AsyncSession) -> uuid.UUID:
    sid = uuid.uuid4()
    await db.execute(
        text(
            "INSERT INTO stations (id, rb_uuid, slug, name, status, source, updated_at) "
            "VALUES (:id, :rb, :slug, 'X', 'active', 'radio-browser', :old)"
        ),
        {"id": sid, "rb": uuid.uuid4(), "slug": f"s-{sid.hex[:8]}", "old": OLD},
    )
    await db.commit()
    return sid


async def _genres(db: AsyncSession, *slugs: str) -> list[int]:
    ids = []
    for slug in slugs:
        row = (
            await db.execute(
                text(
                    "INSERT INTO genres (slug, name, color_hex) VALUES (:s, :s, '#ffffff') "
                    "ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name RETURNING id"
                ),
                {"s": slug},
            )
        ).one()
        ids.append(int(row[0]))
    await db.commit()
    return ids


async def _links(db: AsyncSession, sid: uuid.UUID) -> dict[int, tuple[int, str]]:
    db.expire_all()
    rows = (
        await db.execute(
            text("SELECT genre_id, confidence, source FROM station_genres WHERE station_id = :s"),
            {"s": sid},
        )
    ).all()
    return {r[0]: (r[1], r[2]) for r in rows}


async def _updated_at(db: AsyncSession, sid: uuid.UUID) -> datetime:
    db.expire_all()
    return (
        await db.execute(text("SELECT updated_at FROM stations WHERE id = :i"), {"i": sid})
    ).one()[0]


async def _replace(db: AsyncSession, sid: uuid.UUID, matches: list[tuple[int, int]]) -> SyncStats:
    stats = SyncStats()
    await replace_rb_tag_links(db, sid, matches, stats=stats)
    await db.commit()
    return stats


async def test_same_matches_again_changes_nothing_and_keeps_updated_at(
    db_session: AsyncSession,
) -> None:
    sid = await _station(db_session)
    a, b = await _genres(db_session, "rl-a", "rl-b")
    await _replace(db_session, sid, [(a, 80), (b, 60)])
    await db_session.execute(
        text("UPDATE stations SET updated_at = :t WHERE id = :i"), {"t": OLD, "i": sid}
    )
    await db_session.commit()

    stats = await _replace(db_session, sid, [(a, 80), (b, 60)])

    assert await _links(db_session, sid) == {a: (80, "rb_tag"), b: (60, "rb_tag")}
    assert await _updated_at(db_session, sid) == OLD
    assert stats.genre_links == 2


async def test_added_and_removed_genres_do_move_updated_at(db_session: AsyncSession) -> None:
    sid = await _station(db_session)
    a, b, c = await _genres(db_session, "rl-a", "rl-b", "rl-c")
    await _replace(db_session, sid, [(a, 80), (b, 60)])
    await db_session.execute(
        text("UPDATE stations SET updated_at = :t WHERE id = :i"), {"t": OLD, "i": sid}
    )
    await db_session.commit()

    await _replace(db_session, sid, [(a, 80), (c, 50)])  # b fuera, c dentro

    assert await _links(db_session, sid) == {a: (80, "rb_tag"), c: (50, "rb_tag")}
    assert await _updated_at(db_session, sid) > OLD


async def test_confidence_change_updates_the_row_without_moving_updated_at(
    db_session: AsyncSession,
) -> None:
    sid = await _station(db_session)
    (a,) = await _genres(db_session, "rl-a")
    await _replace(db_session, sid, [(a, 80)])
    await db_session.execute(
        text("UPDATE stations SET updated_at = :t WHERE id = :i"), {"t": OLD, "i": sid}
    )
    await db_session.commit()

    await _replace(db_session, sid, [(a, 55)])

    assert await _links(db_session, sid) == {a: (55, "rb_tag")}
    assert await _updated_at(db_session, sid) == OLD


async def test_manual_genres_are_never_touched(db_session: AsyncSession) -> None:
    sid = await _station(db_session)
    a, b = await _genres(db_session, "rl-a", "rl-b")
    await db_session.execute(
        text(
            "INSERT INTO station_genres (station_id, genre_id, source, confidence) VALUES (:s, :g, 'manual', 100)"
        ),
        {"s": sid, "g": a},
    )
    await db_session.commit()

    await _replace(db_session, sid, [(a, 80), (b, 60)])  # a ya es manual: no se pisa

    assert await _links(db_session, sid) == {a: (100, "manual"), b: (60, "rb_tag")}
    await _replace(db_session, sid, [])  # sin matches: quita solo los rb_tag
    assert await _links(db_session, sid) == {a: (100, "manual")}
