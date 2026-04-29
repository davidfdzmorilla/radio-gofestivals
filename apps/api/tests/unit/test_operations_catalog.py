from __future__ import annotations

import pytest

from app.services.admin.operations_catalog import (
    ALLOWED_COMMANDS,
    AutoCurateParams,
    NoParams,
    params_to_argv,
)


def test_catalog_has_expected_commands() -> None:
    assert set(ALLOWED_COMMANDS) == {
        "rb_sync_run",
        "rb_sync_health_check",
        "auto_curate",
        "compute_quality_scores",
        "snapshot_clickcounts",
        "compute_click_trends",
    }
    for spec in ALLOWED_COMMANDS.values():
        assert "argv_base" in spec
        assert "timeout" in spec
        assert "params_model" in spec
        assert "label" in spec
        assert "description" in spec


def test_params_to_argv_translates_kebab_case() -> None:
    argv = params_to_argv(
        {"min_quality": 70, "limit": 50, "admin_email": "a@b.com"},
    )
    # order is insertion order
    assert argv == [
        "--min-quality",
        "70",
        "--limit",
        "50",
        "--admin-email",
        "a@b.com",
    ]


def test_params_to_argv_bool_true_emits_flag() -> None:
    assert params_to_argv({"dry_run": True}) == ["--dry-run"]


def test_params_to_argv_bool_false_omits_flag() -> None:
    assert params_to_argv({"dry_run": False}) == []


def test_params_to_argv_drops_none() -> None:
    assert params_to_argv({"country": None, "limit": 10}) == ["--limit", "10"]


def test_params_to_argv_empty_or_none() -> None:
    assert params_to_argv(None) == []
    assert params_to_argv({}) == []


def test_no_params_accepts_empty() -> None:
    assert NoParams().model_dump() == {}


def test_auto_curate_validates_required_admin_email() -> None:
    with pytest.raises(Exception):
        AutoCurateParams(min_quality=70, limit=10)


def test_auto_curate_defaults() -> None:
    p = AutoCurateParams(admin_email="a@b.com")
    assert p.min_quality == 60
    assert p.limit == 50
    assert p.country is None
    assert p.dry_run is False


def test_auto_curate_rejects_min_quality_out_of_range() -> None:
    with pytest.raises(Exception):
        AutoCurateParams(admin_email="a@b.com", min_quality=200)
