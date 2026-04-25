from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from scripts.rb_sync import parse_iso_datetime, parse_uuid


# --- parse_uuid -------------------------------------------------------------


def test_parse_uuid_valid_string() -> None:
    raw = "12345678-1234-5678-1234-567812345678"
    assert parse_uuid(raw) == uuid.UUID(raw)


def test_parse_uuid_invalid_returns_none() -> None:
    assert parse_uuid("not-a-uuid") is None
    assert parse_uuid("") is None
    assert parse_uuid(None) is None
    assert parse_uuid(0) is None


# --- parse_iso_datetime -----------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-04-25 16:34:58", datetime(2026, 4, 25, 16, 34, 58, tzinfo=UTC)),
        ("2026-04-25T16:34:58", datetime(2026, 4, 25, 16, 34, 58, tzinfo=UTC)),
        ("2026-04-25T16:34:58Z", datetime(2026, 4, 25, 16, 34, 58, tzinfo=UTC)),
        (
            "2026-04-25T16:34:58+00:00",
            datetime(2026, 4, 25, 16, 34, 58, tzinfo=UTC),
        ),
    ],
)
def test_parse_iso_datetime_known_formats(raw: str, expected: datetime) -> None:
    assert parse_iso_datetime(raw) == expected


def test_parse_iso_datetime_invalid_returns_none() -> None:
    assert parse_iso_datetime("") is None
    assert parse_iso_datetime(None) is None
    assert parse_iso_datetime("garbage") is None
    assert parse_iso_datetime("2026-99-99") is None
