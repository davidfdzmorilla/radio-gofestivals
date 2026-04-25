from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from scripts.dedupe_stations import (
    StationRow,
    codec_rank,
    dedupe_key,
    dedupe_run,
    normalize_name,
    pick_best,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# --- Pure helpers -----------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Techno Tribe", "techno tribe"),
        ("- 0 N - Dance on Radio", "0 n - dance on radio"),
        ("  Multi   Spaces  ", "multi spaces"),
        ("—Trance Energy", "trance energy"),
        ("•·_Dub FM", "dub fm"),
    ],
)
def test_normalize_name(raw: str, expected: str) -> None:
    assert normalize_name(raw) == expected


def test_codec_rank_orders_correctly() -> None:
    assert codec_rank("opus") > codec_rank("aac+")
    assert codec_rank("aac+") == codec_rank("aacp")
    assert codec_rank("aac+") > codec_rank("aac")
    assert codec_rank("aac") > codec_rank("mp3")
    assert codec_rank("mp3") > codec_rank("flac")  # unknown but non-null
    assert codec_rank("MP3") == codec_rank("mp3")
    assert codec_rank(None) == 0


def _row(
    *,
    name: str = "X",
    country: str | None = "ES",
    homepage: str | None = "https://x",
    bitrate: int | None = 128,
    codec: str | None = "mp3",
    quality: int = 50,
    created: datetime | None = None,
    rid: str | None = None,
) -> StationRow:
    return StationRow(
        id=rid or str(uuid.uuid4()),
        name=name,
        country_code=country,
        homepage_url=homepage,
        bitrate=bitrate,
        codec=codec,
        quality_score=quality,
        created_at=created or datetime(2026, 1, 1, tzinfo=UTC),
        status="active",
    )


def test_dedupe_key_groups_null_homepage_with_anything() -> None:
    a = _row(name="Sub FM", country="GB", homepage=None)
    b = _row(name="sub fm", country="gb", homepage=None)
    assert dedupe_key(a) == dedupe_key(b)


def test_dedupe_key_separates_different_countries() -> None:
    a = _row(name="Trance Radio", country="DE", homepage="https://t.de")
    b = _row(name="Trance Radio", country="PL", homepage="https://t.de")
    assert dedupe_key(a) != dedupe_key(b)


def test_pick_best_prefers_higher_bitrate() -> None:
    low = _row(bitrate=64, codec="opus")
    high = _row(bitrate=320, codec="mp3")
    assert pick_best([low, high]).id == high.id


def test_pick_best_falls_back_to_codec_then_quality_then_age() -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    a = _row(bitrate=128, codec="mp3", quality=50, created=base, rid="a")
    b = _row(bitrate=128, codec="aac", quality=50, created=base, rid="b")
    assert pick_best([a, b]).id == "b"  # codec breaks tie

    c = _row(bitrate=128, codec="mp3", quality=70, created=base, rid="c")
    d = _row(bitrate=128, codec="mp3", quality=40, created=base, rid="d")
    assert pick_best([c, d]).id == "c"  # quality breaks tie

    older = _row(bitrate=128, codec="mp3", quality=50, created=base, rid="older")
    newer = _row(
        bitrate=128, codec="mp3", quality=50, created=base + timedelta(days=10), rid="newer",
    )
    assert pick_best([older, newer]).id == "older"  # older wins


def test_pick_best_is_deterministic() -> None:
    rows = [
        _row(bitrate=128, codec="mp3", quality=50, rid="a"),
        _row(bitrate=320, codec="aac", quality=80, rid="b"),
        _row(bitrate=320, codec="opus", quality=70, rid="c"),
    ]
    first = pick_best(rows).id
    for _ in range(5):
        assert pick_best(rows).id == first


# --- Integration test against real DB ---------------------------------------


async def _insert_station(
    session: AsyncSession,
    *,
    name: str,
    slug: str,
    bitrate: int,
    codec: str,
    quality: int = 50,
    homepage: str | None = "https://example.com",
    country: str = "ES",
) -> uuid.UUID:
    result = await session.execute(
        text(
            """
            INSERT INTO stations
                (name, slug, stream_url, homepage_url, country_code,
                 bitrate, codec, quality_score, status, source)
            VALUES
                (:name, :slug, :stream, :hp, :cc,
                 :br, :codec, :q, 'active', 'radio-browser')
            RETURNING id
            """,
        ),
        {
            "name": name,
            "slug": slug,
            "stream": f"https://stream/{slug}.mp3",
            "hp": homepage,
            "cc": country,
            "br": bitrate,
            "codec": codec,
            "q": quality,
        },
    )
    sid = result.scalar_one()
    await session.commit()
    return sid


async def test_dedupe_run_marks_losers_and_keeps_winner(db_session: AsyncSession) -> None:
    keeper = await _insert_station(
        db_session, name="Sub FM", slug="sub-fm-1", bitrate=320, codec="aac+", quality=80,
    )
    loser = await _insert_station(
        db_session, name="Sub FM", slug="sub-fm-2", bitrate=128, codec="mp3", quality=20,
    )
    unrelated = await _insert_station(
        db_session, name="Other Station", slug="other-1", bitrate=128, codec="mp3",
    )

    stats = await dedupe_run(db_session, dry_run=False)

    assert stats.groups_with_duplicates == 1
    assert stats.marked_duplicate == 1

    statuses = dict(
        (
            await db_session.execute(text("SELECT id, status FROM stations"))
        ).all(),
    )
    assert statuses[keeper] == "active"
    assert statuses[loser] == "duplicate"
    assert statuses[unrelated] == "active"


async def test_dedupe_run_dry_run_does_not_mutate(db_session: AsyncSession) -> None:
    a = await _insert_station(
        db_session, name="Same Name", slug="sn-1", bitrate=320, codec="aac+",
    )
    b = await _insert_station(
        db_session, name="Same Name", slug="sn-2", bitrate=128, codec="mp3",
    )

    stats = await dedupe_run(db_session, dry_run=True)
    assert stats.marked_duplicate == 1

    statuses = dict(
        (
            await db_session.execute(
                text("SELECT id, status FROM stations WHERE id IN (:a, :b)"),
                {"a": a, "b": b},
            )
        ).all(),
    )
    assert statuses[a] == "active"
    assert statuses[b] == "active"
