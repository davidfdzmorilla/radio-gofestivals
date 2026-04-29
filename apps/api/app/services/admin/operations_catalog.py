"""Whitelist of CLI commands the admin UI is allowed to enqueue.

The same catalog (with executable argv only) lives in
`packages/scripts/scripts/run_pending_admin_jobs.py`. Both must stay
in sync — there is no cross-package import to enforce that.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class NoParams(BaseModel):
    """Marker schema for commands that take no parameters."""


class AutoCurateParams(BaseModel):
    admin_email: str = Field(min_length=1)
    min_quality: int = Field(default=60, ge=0, le=100)
    limit: int = Field(default=50, ge=1, le=500)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    dry_run: bool = False


CommandKey = Literal[
    "rb_sync_run",
    "rb_sync_health_check",
    "auto_curate",
    "compute_quality_scores",
    "snapshot_clickcounts",
    "compute_click_trends",
]


# Each entry holds:
#   - argv_base: list[str] passed to subprocess.run()
#   - timeout: per-command wall clock limit (seconds)
#   - params_model: Pydantic schema for the JSON params blob
#   - label/description: shown in the catalog endpoint
#
# `params_to_argv` translates the validated params dict into CLI flags:
# `min_quality=70` → ["--min-quality", "70"]; bool=True → ["--flag"];
# bool=False / None are dropped.
ALLOWED_COMMANDS: dict[str, dict[str, Any]] = {
    "rb_sync_run": {
        "argv_base": ["rb_sync", "run"],
        "timeout": 600,
        "params_model": NoParams,
        "label": "Run sync",
        "description": "Sincronización completa con Radio-Browser.",
    },
    "rb_sync_health_check": {
        "argv_base": ["rb_sync", "health-check"],
        "timeout": 1800,
        "params_model": NoParams,
        "label": "Run health-check",
        "description": "Verificar todos los streams.",
    },
    "auto_curate": {
        "argv_base": ["rb_sync", "auto-curate-top"],
        "timeout": 300,
        "params_model": AutoCurateParams,
        "label": "Auto-curate top stations",
        "description": (
            "Promover stations pending con quality_score >= threshold."
        ),
    },
    "compute_quality_scores": {
        "argv_base": ["compute-quality-scores"],
        "timeout": 120,
        "params_model": NoParams,
        "label": "Recompute quality scores",
        "description": "Recalcular quality_score de stations active.",
    },
    "snapshot_clickcounts": {
        "argv_base": ["snapshot-clickcounts"],
        "timeout": 60,
        "params_model": NoParams,
        "label": "Snapshot clickcounts",
        "description": "Capturar clickcount actual al historial.",
    },
    "compute_click_trends": {
        "argv_base": ["compute-click-trends"],
        "timeout": 120,
        "params_model": NoParams,
        "label": "Recompute click trends",
        "description": "Recalcular click_trend (ratio 7-day) por station.",
    },
}


def params_to_argv(params: dict[str, Any] | None) -> list[str]:
    """Translate a validated params dict to CLI flags.

    Mirrors the Click/Typer convention used by the existing scripts
    (snake_case key → kebab-case flag). Bool values become a present
    flag when True and are omitted when False.
    """
    if not params:
        return []
    argv: list[str] = []
    for key, value in params.items():
        flag = "--" + str(key).replace("_", "-")
        if isinstance(value, bool):
            if value:
                argv.append(flag)
            continue
        if value is None:
            continue
        argv.extend([flag, str(value)])
    return argv
