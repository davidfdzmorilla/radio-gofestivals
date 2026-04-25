from __future__ import annotations

import pytest

from scripts.quality import (
    compute_popularity_score,
    compute_quality_score,
    compute_reliability_score,
    compute_technical_score,
)


# --- technical_score --------------------------------------------------------


def test_technical_score_at_bounds() -> None:
    assert compute_technical_score(32, "mp3") == 0
    assert compute_technical_score(320, "mp3") == 100


def test_technical_score_below_floor_is_zero() -> None:
    assert compute_technical_score(0, "mp3") == 0
    assert compute_technical_score(None, "mp3") == 0


def test_technical_score_above_ceiling_is_capped() -> None:
    assert compute_technical_score(1000, "mp3") == 100


def test_technical_score_codec_boost() -> None:
    base = compute_technical_score(128, "mp3")
    aac = compute_technical_score(128, "aac+")
    opus = compute_technical_score(128, "opus")
    assert aac > base
    assert opus > aac


def test_technical_score_codec_case_insensitive() -> None:
    assert compute_technical_score(128, "OPUS") == compute_technical_score(128, "opus")
    assert compute_technical_score(128, "AAC+") == compute_technical_score(128, "aac+")


def test_technical_score_unknown_codec_penalised_below_mp3() -> None:
    assert compute_technical_score(128, "wmav2") < compute_technical_score(128, "mp3")
    assert compute_technical_score(128, None) < compute_technical_score(128, "mp3")


# --- popularity_score -------------------------------------------------------


def test_popularity_score_zero_when_no_signal() -> None:
    assert compute_popularity_score(0, 0) == 0
    assert compute_popularity_score(None, None) == 0


def test_popularity_score_grows_with_clicks_and_votes() -> None:
    low = compute_popularity_score(10, 5)
    mid = compute_popularity_score(500, 50)
    high = compute_popularity_score(10_000, 1000)
    assert low < mid < high
    assert high <= 100


def test_popularity_score_caps_at_100() -> None:
    # log10(100M) × 25 = 200 → capped to 100
    assert compute_popularity_score(100_000_000, 1_000_000) == 100


# --- reliability_score ------------------------------------------------------


@pytest.mark.parametrize(
    ("fails", "expected"),
    [(0, 100), (1, 80), (2, 60), (3, 40), (4, 20), (5, 0), (10, 0), (None, 100)],
)
def test_reliability_score_stepwise(fails: int | None, expected: int) -> None:
    assert compute_reliability_score(fails) == expected


# --- quality_score (composite) ----------------------------------------------


def test_quality_top_tier_close_to_100() -> None:
    s = compute_quality_score({
        "bitrate": 320, "codec": "opus",
        "clickcount": 10000, "votes": 1000,
        "failed_checks": 0, "status": "active",
    })
    assert 90 <= s <= 100


def test_quality_low_tier_around_30() -> None:
    s = compute_quality_score({
        "bitrate": 64, "codec": "mp3",
        "clickcount": 10, "votes": 0,
        "failed_checks": 0, "status": "active",
    })
    assert 25 <= s <= 45


def test_quality_mid_tier_around_60() -> None:
    s = compute_quality_score({
        "bitrate": 128, "codec": "aac+",
        "clickcount": 500, "votes": 50,
        "failed_checks": 0, "status": "active",
    })
    assert 50 <= s <= 70


def test_quality_all_null_yields_only_reliability_floor() -> None:
    # technical=0, popularity=0, reliability=100, weights → 20
    s = compute_quality_score({
        "bitrate": None, "codec": None,
        "clickcount": None, "votes": None,
        "failed_checks": None, "status": "active",
    })
    assert s == 20


def test_quality_high_failed_checks_pulls_score_down() -> None:
    base = compute_quality_score({
        "bitrate": 320, "codec": "opus",
        "clickcount": 1000, "votes": 100,
        "failed_checks": 0, "status": "active",
    })
    broken_streak = compute_quality_score({
        "bitrate": 320, "codec": "opus",
        "clickcount": 1000, "votes": 100,
        "failed_checks": 10, "status": "active",
    })
    assert broken_streak < base
    # reliability drops from 100 to 0, that's -20pts of weighted contribution
    assert base - broken_streak >= 18


def test_quality_broken_status_is_zero() -> None:
    s = compute_quality_score({
        "bitrate": 320, "codec": "opus",
        "clickcount": 99999, "votes": 9999,
        "failed_checks": 0, "status": "broken",
    })
    assert s == 0


def test_quality_duplicate_status_is_zero() -> None:
    s = compute_quality_score({
        "bitrate": 320, "codec": "opus",
        "clickcount": 99999, "votes": 9999,
        "failed_checks": 0, "status": "duplicate",
    })
    assert s == 0


def test_quality_is_deterministic() -> None:
    payload = {
        "bitrate": 192, "codec": "aac",
        "clickcount": 250, "votes": 30,
        "failed_checks": 1, "status": "active",
    }
    first = compute_quality_score(payload)
    for _ in range(5):
        assert compute_quality_score(payload) == first


def test_quality_is_in_valid_range_for_random_inputs() -> None:
    cases = [
        {"bitrate": b, "codec": c, "clickcount": cc, "votes": v,
         "failed_checks": f, "status": "active"}
        for b in (None, 32, 96, 192, 320, 1000)
        for c in (None, "mp3", "aac", "aac+", "opus", "flac")
        for cc in (None, 0, 1, 50, 999, 1_000_000)
        for v in (None, 0, 5, 1000)
        for f in (None, 0, 3, 99)
    ]
    for case in cases:
        s = compute_quality_score(case)
        assert 0 <= s <= 100, f"out of range for {case}: {s}"
