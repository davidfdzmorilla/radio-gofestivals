"""stations.updated_at solo avanza con cambios de contenido (migración 0027)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

OLD = datetime(2026, 1, 1, tzinfo=UTC)


async def _station(db: AsyncSession) -> uuid.UUID:
    sid = uuid.uuid4()
    await db.execute(
        text(
            "INSERT INTO stations (id, rb_uuid, slug, name, status, source, country_code, "
            "city, geo, updated_at) VALUES (:id, :rb, :slug, 'Radio X', 'active', "
            "'radio-browser', 'DE', 'Berlin', "
            "ST_SetSRID(ST_MakePoint(13.4, 52.5), 4326)::geography, :old)"
        ),
        {"id": sid, "rb": uuid.uuid4(), "slug": f"s-{sid.hex[:8]}", "old": OLD},
    )
    await db.commit()
    return sid


async def _updated_at(db: AsyncSession, sid: uuid.UUID) -> datetime:
    db.expire_all()
    row = (await db.execute(text("SELECT updated_at FROM stations WHERE id = :i"), {"i": sid})).one()
    return row[0]


async def _update(db: AsyncSession, sid: uuid.UUID, sets: str, **params: Any) -> None:
    stmt = f"UPDATE stations SET {sets} WHERE id = :sid"  # noqa: S608 - literales del propio test
    await db.execute(text(stmt), {"sid": sid, **params})
    await db.commit()


OPERATIONAL = [
    ("last_check_at = now(), last_check_ok = now()", {}),  # health-check ok
    ("last_check_at = now(), last_error = 'timeout'", {}),  # health-check ko
    ("failed_checks = failed_checks + 1", {}),
    ("quality_score = 12", {}),
    ("click_trend = 3.5", {}),
    ("clickcount = 999, votes = 4, votes_local = 2", {}),
    ("rb_tags = ARRAY['techno','house']", {}),
    ("electronic_score = 90, class_reason = 'x', class_source = 'rule', classified_at = now()", {}),
    ("curated = true", {}),
    # reescribir los mismos valores (el sync diario lo hace) tampoco cuenta
    ("name = name, slug = slug, country_code = country_code, hidden = hidden", {}),
]

CONTENT = [
    ("name = 'Otro nombre'", {}),
    ("slug = 'nuevo-slug'", {}),
    ("logo_hash = 'abc123'", {}),
    ("favicon_url = 'https://x/y.png'", {}),
    ("homepage_url = 'https://x'", {}),
    ("country_code = 'FR'", {}),
    ("city = 'Paris'", {}),
    ("language = 'french'", {}),
    ("geo = ST_SetSRID(ST_MakePoint(2.3, 48.8), 4326)::geography", {}),
    ("hidden = true", {}),
    ("status = 'broken'", {}),
    ("class_state = 'rejected'", {}),
]


@pytest.mark.parametrize(("sets", "params"), OPERATIONAL)
async def test_operational_updates_do_not_move_updated_at(
    db_session: AsyncSession, sets: str, params: dict[str, Any]
) -> None:
    sid = await _station(db_session)
    await _update(db_session, sid, sets, **params)
    assert await _updated_at(db_session, sid) == OLD


@pytest.mark.parametrize(("sets", "params"), CONTENT)
async def test_content_updates_move_updated_at(
    db_session: AsyncSession, sets: str, params: dict[str, Any]
) -> None:
    sid = await _station(db_session)
    await _update(db_session, sid, sets, **params)
    assert await _updated_at(db_session, sid) > OLD


async def test_an_explicit_updated_at_is_respected(db_session: AsyncSession) -> None:
    sid = await _station(db_session)
    explicit = OLD + timedelta(days=30)
    await _update(db_session, sid, "quality_score = 70, updated_at = :t", t=explicit)
    assert await _updated_at(db_session, sid) == explicit


async def _genre(db: AsyncSession, slug: str) -> int:
    row = (
        await db.execute(
            text(
                "INSERT INTO genres (slug, name, color_hex) VALUES (:s, :s, '#ffffff') "
                "ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name RETURNING id"
            ),
            {"s": slug},
        )
    ).one()
    await db.commit()
    return int(row[0])


async def test_genre_changes_move_updated_at(db_session: AsyncSession) -> None:
    sid = await _station(db_session)
    g1, g2 = await _genre(db_session, "trg-a"), await _genre(db_session, "trg-b")

    async def reset() -> None:
        await _update(db_session, sid, "updated_at = :t", t=OLD)

    await db_session.execute(
        text("INSERT INTO station_genres (station_id, genre_id, source) VALUES (:s, :g, 'rb_tag')"),
        {"s": sid, "g": g1},
    )
    await db_session.commit()
    assert await _updated_at(db_session, sid) > OLD  # género añadido

    await reset()
    await db_session.execute(
        text("UPDATE station_genres SET confidence = 10 WHERE station_id = :s"), {"s": sid}
    )
    await db_session.commit()
    assert await _updated_at(db_session, sid) == OLD  # solo la confianza: no cuenta

    await db_session.execute(
        text("UPDATE station_genres SET genre_id = :g WHERE station_id = :s"), {"s": sid, "g": g2}
    )
    await db_session.commit()
    assert await _updated_at(db_session, sid) > OLD  # género cambiado

    await reset()
    await db_session.execute(text("DELETE FROM station_genres WHERE station_id = :s"), {"s": sid})
    await db_session.commit()
    assert await _updated_at(db_session, sid) > OLD  # género quitado


async def test_deleting_a_station_with_genres_does_not_fail(db_session: AsyncSession) -> None:
    sid = await _station(db_session)
    g = await _genre(db_session, "trg-c")
    await db_session.execute(
        text("INSERT INTO station_genres (station_id, genre_id, source) VALUES (:s, :g, 'manual')"),
        {"s": sid, "g": g},
    )
    await db_session.commit()
    await db_session.execute(text("DELETE FROM stations WHERE id = :s"), {"s": sid})
    await db_session.commit()
