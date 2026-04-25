"""quality_score computation.

Combines three signals on a 0-100 scale:

  technical    50%  bitrate × codec factor
  popularity   30%  log10(clickcount) + log10(votes)
  reliability  20%  inverse of failed_checks

stations with status in {'broken', 'duplicate'} score 0 regardless of
the underlying signals — a broken stream is worthless even if its
metadata looks great, and a duplicate is by definition shadowed by
another row that should rank higher.
"""
from __future__ import annotations

import math
from typing import Any

# Higher == better. Multiplies bitrate_score.
_CODEC_FACTOR: dict[str, float] = {
    "opus": 1.15,
    "aac+": 1.10,
    "aacp": 1.10,
    "aac": 1.10,
    "mp3": 1.00,
}
_UNKNOWN_CODEC_FACTOR = 0.85

_DEAD_STATUSES: frozenset[str] = frozenset({"broken", "duplicate"})


def compute_technical_score(bitrate: int | None, codec: str | None) -> int:
    """Linear bitrate score in [0, 100] tuned by codec efficiency.

    Scale anchors:
      - bitrate <= 32 kbps    → 0 (telephony quality, sub-FM)
      - bitrate >= 320 kbps   → 100 (FM-broadcast-grade)
      - in between            → linear
    """
    if bitrate is None or bitrate <= 0:
        return 0
    clamped = max(32, min(320, bitrate))
    bitrate_score = (clamped - 32) / (320 - 32) * 100
    factor = _UNKNOWN_CODEC_FACTOR
    if codec is not None:
        factor = _CODEC_FACTOR.get(codec.strip().lower(), _UNKNOWN_CODEC_FACTOR)
    return int(min(100, round(bitrate_score * factor)))


def _log_score(value: int | None, *, multiplier: float) -> float:
    """log10(value+1) × multiplier, clamped to [0, 100]."""
    if value is None or value <= 0:
        return 0.0
    return min(100.0, math.log10(value + 1) * multiplier)


def compute_popularity_score(clickcount: int | None, votes: int | None) -> int:
    """Log-scaled popularity: 60% clicks, 40% votes.

    Anchors (after log10):
      - clickcount 10000 → 100, 100 → 50, 10 → 25
      - votes 1000 → 90, 100 → 60, 10 → 30
    """
    click_score = _log_score(clickcount, multiplier=25.0)
    vote_score = _log_score(votes, multiplier=30.0)
    combined = click_score * 0.6 + vote_score * 0.4
    return int(round(combined))


def compute_reliability_score(failed_checks: int | None) -> int:
    """Step function: 100 at 0 fails, 0 at >=5 fails, -20 per fail in between."""
    if failed_checks is None or failed_checks <= 0:
        return 100
    if failed_checks >= 5:
        return 0
    return 100 - failed_checks * 20


def compute_quality_score(station: dict[str, Any]) -> int:
    """Compute final quality_score in [0, 100] from a station dict.

    Expected keys (all optional, missing == None):
      - bitrate, codec, clickcount, votes, failed_checks, status
    """
    status = station.get("status")
    if status in _DEAD_STATUSES:
        return 0

    technical = compute_technical_score(station.get("bitrate"), station.get("codec"))
    popularity = compute_popularity_score(
        station.get("clickcount"), station.get("votes"),
    )
    reliability = compute_reliability_score(station.get("failed_checks"))

    weighted = technical * 0.50 + popularity * 0.30 + reliability * 0.20
    return max(0, min(100, int(round(weighted))))
