"""run-pending-admin-jobs · process one pending admin_jobs row.

The host cron invokes this every minute. It claims a single
`admin_jobs` row with `FOR UPDATE SKIP LOCKED`, runs the matching
CLI command via subprocess with a per-command timeout, captures the
stdout's last JSON line as `result_json`, and writes the outcome
back to the row.

The whitelist below MUST stay in sync with
`apps/api/app/services/admin/operations_catalog.py::ALLOWED_COMMANDS`.
There is no cross-package import — when a new command is added on
the API side, the same `argv_base` and `timeout` must be added here.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from typing import TYPE_CHECKING, Any

import typer
from sqlalchemy import text

from scripts.db import make_engine, make_sessionmaker
from scripts.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession


log = get_logger("scripts.run_pending_admin_jobs")
app = typer.Typer(help="radio.gofestivals · process pending admin jobs")


_ALLOWED_COMMANDS: dict[str, dict[str, Any]] = {
    "rb_sync_run": {
        "argv_base": ["rb_sync", "run"],
        "timeout": 600,
    },
    "rb_sync_health_check": {
        "argv_base": ["rb_sync", "health-check"],
        "timeout": 1800,
    },
    "auto_curate": {
        "argv_base": ["rb_sync", "auto-curate-top"],
        "timeout": 300,
    },
    "compute_quality_scores": {
        "argv_base": ["compute-quality-scores"],
        "timeout": 120,
    },
    "snapshot_clickcounts": {
        "argv_base": ["snapshot-clickcounts"],
        "timeout": 60,
    },
    "compute_click_trends": {
        "argv_base": ["compute-click-trends"],
        "timeout": 120,
    },
}


def _params_to_argv(params: dict[str, Any] | None) -> list[str]:
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


def _parse_last_json_event(stdout: str) -> dict[str, Any] | None:
    """Return the last line of stdout that is a JSON object."""
    for raw in reversed(stdout.splitlines()):
        line = raw.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _execute(argv: list[str], timeout: int) -> dict[str, Any]:
    try:
        result = subprocess.run(  # noqa: S603
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        partial_err = ""
        if exc.stderr:
            data = exc.stderr
            partial_err = (
                data.decode("utf-8", errors="replace")
                if isinstance(data, bytes)
                else str(data)
            )
        return {
            "status": "timeout",
            "result_json": None,
            "stderr_tail": (
                f"Timeout after {timeout}s.\n"
                f"Last stderr:\n{partial_err[-2000:]}"
            ),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "failed",
            "result_json": None,
            "stderr_tail": f"Worker exception: {type(exc).__name__}: {exc}",
        }

    result_json = _parse_last_json_event(result.stdout or "")
    stderr_tail: str | None = None
    if result.returncode != 0 and result.stderr:
        lines = result.stderr.splitlines()
        stderr_tail = "\n".join(lines[-50:])
    job_status = "success" if result.returncode == 0 else "failed"
    return {
        "status": job_status,
        "result_json": result_json,
        "stderr_tail": stderr_tail,
    }


async def _process_one(
    maker: async_sessionmaker[AsyncSession],
) -> int:
    """Process at most one pending job. Returns 0 if processed, 1 if idle."""
    async with maker() as session:
        row = (
            await session.execute(
                text(
                    """
                    UPDATE admin_jobs
                    SET status = 'running', started_at = now()
                    WHERE id = (
                        SELECT id FROM admin_jobs
                        WHERE status = 'pending'
                        ORDER BY created_at ASC
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                    )
                    RETURNING id, command, params_json
                    """,
                ),
            )
        ).first()
        if row is None:
            await session.commit()
            log.info("no_pending_jobs")
            return 1

        job_id = int(row[0])
        command = str(row[1])
        params_json: dict[str, Any] | None = row[2]
        await session.commit()

    log.info("job_claimed", job_id=job_id, command=command)

    spec = _ALLOWED_COMMANDS.get(command)
    if spec is None:
        async with maker() as session:
            await session.execute(
                text(
                    """
                    UPDATE admin_jobs
                    SET status='failed',
                        finished_at = now(),
                        stderr_tail = 'Unknown command in worker catalog'
                    WHERE id = :id
                    """,
                ),
                {"id": job_id},
            )
            await session.commit()
        log.warning("unknown_command", job_id=job_id, command=command)
        return 0

    argv = list(spec["argv_base"]) + _params_to_argv(params_json)
    log.info("executing", job_id=job_id, argv=argv)
    outcome = _execute(argv, int(spec["timeout"]))

    async with maker() as session:
        await session.execute(
            text(
                """
                UPDATE admin_jobs
                SET status = :status,
                    finished_at = now(),
                    result_json = CAST(:result AS jsonb),
                    stderr_tail = :stderr
                WHERE id = :id
                """,
            ),
            {
                "id": job_id,
                "status": outcome["status"],
                "result": (
                    json.dumps(outcome["result_json"])
                    if outcome["result_json"] is not None
                    else None
                ),
                "stderr": outcome["stderr_tail"],
            },
        )
        await session.commit()

    log.info("job_completed", job_id=job_id, status=outcome["status"])
    return 0


@app.command("run")
def cmd_run() -> None:
    """Process one pending job and exit. Idle if none pending."""
    engine = make_engine()
    maker = make_sessionmaker(engine)

    async def _main() -> int:
        try:
            return await _process_one(maker)
        finally:
            await engine.dispose()

    sys.exit(asyncio.run(_main()))


if __name__ == "__main__":
    app()
