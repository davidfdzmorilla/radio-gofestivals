from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import text

from scripts.quality import compute_quality_score
from scripts.quality_cmd import _apply_updates, _fetch_rows

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def _insert(
    session: AsyncSession,
    *,
    slug: str,
    name: str,
    bitrate: int | None,
    codec: str | None,
    status: str = "active",
    failed_checks: int = 0,
    starting_quality: int = 50,
) -> uuid.UUID:
    result = await session.execute(
        text(
            """
            INSERT INTO stations
                (name, slug, stream_url, bitrate, codec, quality_score,
                 status, failed_checks, source)
            VALUES
                (:name, :slug, :stream, :br, :codec, :q,
                 CAST(:st AS station_status), :fc, 'radio-browser')
            RETURNING id
            """,
        ),
        {
            "name": name,
            "slug": slug,
            "stream": f"https://stream/{slug}.mp3",
            "br": bitrate,
            "codec": codec,
            "q": starting_quality,
            "st": status,
            "fc": failed_checks,
        },
    )
    sid = result.scalar_one()
    await session.commit()
    return sid


async def test_compute_quality_scores_updates_active_stations(
    db_session: AsyncSession,
) -> None:
    high = await _insert(
        db_session, slug="hi", name="High Q",
        bitrate=320, codec="opus", failed_checks=0,
    )
    low = await _insert(
        db_session, slug="lo", name="Low Q",
        bitrate=64, codec="mp3", failed_checks=0,
    )
    flaky = await _insert(
        db_session, slug="fl", name="Flaky",
        bitrate=192, codec="aac", failed_checks=4,
    )

    rows = await _fetch_rows(db_session, where_status="active", limit=None)
    pairs: list[tuple[str, int]] = []
    for r in rows:
        pairs.append((str(r["id"]), compute_quality_score(r)))
    await _apply_updates(db_session, pairs)

    scores = dict(
        (
            await db_session.execute(
                text(
                    "SELECT id, quality_score FROM stations WHERE id IN "
                    "(:a, :b, :c)",
                ),
                {"a": high, "b": low, "c": flaky},
            )
        ).all(),
    )
    assert scores[high] > scores[low]
    assert scores[high] > scores[flaky]
    # All three changed off the seeded 50
    assert scores[high] != 50 or scores[low] != 50


async def test_compute_quality_scores_zeroes_broken_and_duplicate(
    db_session: AsyncSession,
) -> None:
    broken = await _insert(
        db_session, slug="br", name="Broken",
        bitrate=320, codec="opus", status="broken",
        starting_quality=80,
    )
    dup = await _insert(
        db_session, slug="dp", name="Dup",
        bitrate=320, codec="opus", status="duplicate",
        starting_quality=80,
    )

    rows = await _fetch_rows(db_session, where_status=None, limit=None)
    pairs = [(str(r["id"]), compute_quality_score(r)) for r in rows]
    await _apply_updates(db_session, pairs)

    scores = dict(
        (
            await db_session.execute(
                text("SELECT id, quality_score FROM stations WHERE id IN (:a, :b)"),
                {"a": broken, "b": dup},
            )
        ).all(),
    )
    assert scores[broken] == 0
    assert scores[dup] == 0


async def test_fetch_rows_respects_status_filter(db_session: AsyncSession) -> None:
    await _insert(
        db_session, slug="a", name="A", bitrate=128, codec="mp3", status="active",
    )
    await _insert(
        db_session, slug="b", name="B", bitrate=128, codec="mp3", status="pending",
    )
    active_rows = await _fetch_rows(db_session, where_status="active", limit=None)
    assert len(active_rows) == 1
    all_rows = await _fetch_rows(db_session, where_status=None, limit=None)
    assert len(all_rows) == 2
