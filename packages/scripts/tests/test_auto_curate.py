from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import bcrypt
import pytest
from sqlalchemy import text

from scripts.rb_sync import run_auto_curate_top

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def _make_admin(
    db_session: AsyncSession,
    email: str = "auto@test.com",
    active: bool = True,
) -> uuid.UUID:
    ph = bcrypt.hashpw(b"test-password-x", bcrypt.gensalt(rounds=4)).decode()
    result = await db_session.execute(
        text(
            """
            INSERT INTO admins (email, password_hash, active, name)
            VALUES (lower(:e), :ph, :active, 'Auto')
            RETURNING id
            """,
        ),
        {"e": email, "ph": ph, "active": active},
    )
    await db_session.commit()
    return uuid.UUID(str(result.scalar_one()))


async def _make_station(
    db_session: AsyncSession,
    *,
    slug: str,
    status: str = "pending",
    quality: int = 70,
    country: str | None = "ES",
    curated: bool = False,
) -> uuid.UUID:
    result = await db_session.execute(
        text(
            """
            INSERT INTO stations (
                slug, name, stream_url, country_code, status, quality_score, curated
            )
            VALUES (
                :slug, :slug, 'https://x/y.mp3', :c,
                CAST(:st AS station_status), :q, :cur
            )
            RETURNING id
            """,
        ),
        {"slug": slug, "c": country, "st": status, "q": quality, "cur": curated},
    )
    await db_session.commit()
    return uuid.UUID(str(result.scalar_one()))


async def test_auto_curate_happy_path(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    await _make_admin(db_session)
    for i, q in enumerate([90, 85, 80, 75, 70, 65, 60, 55, 50, 45]):
        await _make_station(db_session, slug=f"h-{i:02d}", quality=q)

    stats = await run_auto_curate_top(
        maker,
        admin_email="auto@test.com",
        limit=5,
        country=None,
        min_quality=0,
        dry_run=False,
    )
    assert stats.curated == 5

    rows = (
        await db_session.execute(
            text(
                "SELECT slug, curated, status::text, quality_score FROM stations "
                "ORDER BY quality_score DESC",
            ),
        )
    ).all()
    top5 = rows[:5]
    bottom5 = rows[5:]
    for r in top5:
        assert r[1] is True
        assert r[2] == "active"
    for r in bottom5:
        assert r[1] is False
        assert r[2] == "pending"

    log_count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM curation_log WHERE decision = 'approve'"),
        )
    ).scalar_one()
    assert log_count == 5


async def test_auto_curate_respects_country(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    await _make_admin(db_session)
    for i in range(5):
        await _make_station(db_session, slug=f"es-{i}", country="ES", quality=80)
    for i in range(5):
        await _make_station(db_session, slug=f"de-{i}", country="DE", quality=80)

    stats = await run_auto_curate_top(
        maker,
        admin_email="auto@test.com",
        limit=10,
        country="ES",
        min_quality=0,
        dry_run=False,
    )
    assert stats.curated == 5

    curated_slugs = {
        str(r[0])
        for r in (
            await db_session.execute(
                text("SELECT slug FROM stations WHERE curated = true"),
            )
        ).all()
    }
    assert all(s.startswith("es-") for s in curated_slugs)


async def test_auto_curate_respects_min_quality(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    await _make_admin(db_session)
    for i in range(5):
        await _make_station(db_session, slug=f"lo-{i}", quality=40)
    for i in range(5):
        await _make_station(db_session, slug=f"hi-{i}", quality=70)

    stats = await run_auto_curate_top(
        maker,
        admin_email="auto@test.com",
        limit=10,
        country=None,
        min_quality=60,
        dry_run=False,
    )
    assert stats.curated == 5
    assert stats.skipped_below_quality == 5


async def test_auto_curate_idempotent(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    await _make_admin(db_session)
    for i in range(3):
        await _make_station(db_session, slug=f"id-{i}", quality=80)

    s1 = await run_auto_curate_top(
        maker, admin_email="auto@test.com", limit=10,
        country=None, min_quality=0, dry_run=False,
    )
    s2 = await run_auto_curate_top(
        maker, admin_email="auto@test.com", limit=10,
        country=None, min_quality=0, dry_run=False,
    )
    assert s1.curated == 3
    assert s2.curated == 0


async def test_auto_curate_requires_valid_admin(
    maker: async_sessionmaker[AsyncSession],
) -> None:
    with pytest.raises(ValueError, match="admin not found"):
        await run_auto_curate_top(
            maker,
            admin_email="nobody@nowhere.com",
            limit=5,
            country=None,
            min_quality=0,
            dry_run=False,
        )


async def test_auto_curate_rejects_inactive_admin(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    await _make_admin(db_session, email="inactive@test.com", active=False)
    with pytest.raises(ValueError, match="admin not found or inactive"):
        await run_auto_curate_top(
            maker,
            admin_email="inactive@test.com",
            limit=5,
            country=None,
            min_quality=0,
            dry_run=False,
        )


async def test_auto_curate_dry_run_no_writes(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    await _make_admin(db_session)
    for i in range(3):
        await _make_station(db_session, slug=f"dry-{i}", quality=80)

    stats = await run_auto_curate_top(
        maker, admin_email="auto@test.com", limit=10,
        country=None, min_quality=0, dry_run=True,
    )
    assert stats.curated == 3  # stats reflejan lo que se habría curado

    curated = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM stations WHERE curated = true"),
        )
    ).scalar_one()
    assert curated == 0
    log_count = (
        await db_session.execute(text("SELECT COUNT(*) FROM curation_log"))
    ).scalar_one()
    assert log_count == 0


async def test_auto_curate_ignores_active_stations(
    db_session: AsyncSession,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    await _make_admin(db_session)
    await _make_station(
        db_session, slug="already", status="active", quality=99, curated=True,
    )
    await _make_station(db_session, slug="new", status="pending", quality=80)

    stats = await run_auto_curate_top(
        maker, admin_email="auto@test.com", limit=10,
        country=None, min_quality=0, dry_run=False,
    )
    assert stats.curated == 1

    status_map = {
        str(r[0]): (r[1], r[2])
        for r in (
            await db_session.execute(
                text("SELECT slug, status::text, curated FROM stations"),
            )
        ).all()
    }
    assert status_map["already"] == ("active", True)
    assert status_map["new"] == ("active", True)
