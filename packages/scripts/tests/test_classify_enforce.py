from __future__ import annotations

import asyncio
import json
import uuid
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import text
from typer.testing import CliRunner

from scripts.classify_cmd import app
from scripts.classify_enforce import EnforceCapExceededError, enforce
from scripts.db import make_engine, make_sessionmaker

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def _add(
    db: AsyncSession,
    slug: str,
    *,
    state: str | None = "rejected",
    source: str | None = "rule",
    age_h: int = 48,
    curated: bool = False,
    hidden: bool = False,
    hidden_by: str | None = None,
    status: str = "active",
) -> None:
    await db.execute(
        text(
            "INSERT INTO stations (rb_uuid, slug, name, status, source, rb_tags, curated, hidden, "
            "hidden_by, class_state, class_source, classified_at) "
            "VALUES (CAST(:u AS uuid), :s, :s, :st, 'radio-browser', ARRAY['x'], :c, :h, :hb, "
            ":state, :src, now() - make_interval(hours => :age))",
        ),
        {
            "u": str(uuid.uuid4()),
            "s": slug,
            "st": status,
            "c": curated,
            "h": hidden,
            "hb": hidden_by,
            "state": state,
            "src": source,
            "age": age_h,
        },
    )
    await db.commit()


async def _row(db: AsyncSession, slug: str) -> tuple[Any, ...]:
    db.expire_all()
    row = (
        await db.execute(
            text("SELECT hidden, hidden_by FROM stations WHERE slug = :s"), {"s": slug}
        )
    ).first()
    assert row is not None
    return tuple(row)


async def _fill_visible(db: AsyncSession, n: int) -> None:
    for i in range(n):
        await _add(db, f"ok-{i}", state="accepted", source="llm")


async def test_hides_rejected_marks_the_origin_and_leaves_the_rest(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await _fill_visible(db_session, 20)
    await _add(db_session, "rock-rule", source="rule")
    await _add(db_session, "pop-llm", source="llm")
    result = await enforce(maker, dry_run=False, max_change_pct=50)
    assert result.to_hide == 2
    assert await _row(db_session, "rock-rule") == (True, "classifier")
    assert await _row(db_session, "pop-llm") == (True, "classifier")
    assert await _row(db_session, "ok-0") == (False, None)
    assert result.visible_before == 22
    assert result.visible_after == 20


async def test_recent_verdicts_wait_and_min_age_zero_applies_them(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await _fill_visible(db_session, 20)
    await _add(db_session, "fresh", age_h=1)
    result = await enforce(maker, dry_run=False, max_change_pct=50)
    assert (result.to_hide, result.skipped["too_recent"]) == (0, 1)
    assert await _row(db_session, "fresh") == (False, None)
    result = await enforce(maker, dry_run=False, max_change_pct=50, min_age_hours=0)
    assert result.to_hide == 1


async def test_curated_is_hidden_only_by_the_llm_verdict(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await _fill_visible(db_session, 20)
    await _add(db_session, "cur-rule", curated=True, source="rule")
    await _add(db_session, "cur-llm", curated=True, source="llm")
    result = await enforce(maker, dry_run=False, max_change_pct=50)
    assert result.skipped["curated_rule_only"] == 1
    assert await _row(db_session, "cur-rule") == (False, None)
    assert await _row(db_session, "cur-llm") == (True, "classifier")


async def test_manual_decisions_inactive_and_foreign_hides_are_never_touched(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await _fill_visible(db_session, 20)
    await _add(db_session, "manual-no", source="manual")
    await _add(db_session, "broken-no", status="broken")
    # oculta por spam/decisión propia (hidden_by NULL) y con veredicto "accepted": no se repone
    await _add(db_session, "spam", state="accepted", source="llm", hidden=True, hidden_by=None)
    result = await enforce(maker, dry_run=False, max_change_pct=50)
    assert (result.to_hide, result.to_unhide) == (0, 0)
    assert await _row(db_session, "manual-no") == (False, None)
    assert await _row(db_session, "broken-no") == (False, None)
    assert await _row(db_session, "spam") == (True, None)


async def test_reclassified_stations_come_back_but_still_rejected_ones_stay_hidden(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await _fill_visible(db_session, 20)
    await _add(
        db_session, "now-ok", state="accepted", source="llm", hidden=True, hidden_by="classifier"
    )
    await _add(
        db_session, "now-mixed", state="review", source="rule", hidden=True, hidden_by="classifier"
    )
    await _add(
        db_session, "still-no", state="rejected", source="llm", hidden=True, hidden_by="classifier"
    )
    result = await enforce(maker, dry_run=False, max_change_pct=50)
    assert result.to_unhide == 2
    assert await _row(db_session, "now-ok") == (False, None)
    assert await _row(db_session, "now-mixed") == (False, None)
    assert await _row(db_session, "still-no") == (True, "classifier")


async def test_cap_blocks_the_whole_run_and_writes_nothing(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await _fill_visible(db_session, 20)
    for i in range(15):
        await _add(db_session, f"bad-{i}")
    with pytest.raises(EnforceCapExceededError) as exc:
        await enforce(maker, dry_run=False, max_change_pct=5)
    assert exc.value.to_hide == 15
    assert "tope 5 %" in str(exc.value)
    assert await _row(db_session, "bad-0") == (False, None)
    # con el tope subido a propósito sí se aplica
    result = await enforce(maker, dry_run=False, max_change_pct=100)
    assert result.to_hide == 15


async def test_small_hides_pass_even_when_they_exceed_the_percentage(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    # 3 ocultas sobre 8 visibles = 37 %, pero por debajo del mínimo absoluto (10): no se bloquea
    await _fill_visible(db_session, 5)
    for i in range(3):
        await _add(db_session, f"bad-{i}")
    assert (await enforce(maker, dry_run=False, max_change_pct=1)).to_hide == 3


async def test_dry_run_writes_nothing_and_a_second_run_is_idempotent(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await _fill_visible(db_session, 20)
    await _add(db_session, "bad")
    dry = await enforce(maker, dry_run=True, max_change_pct=50)
    assert dry.to_hide == 1
    assert await _row(db_session, "bad") == (False, None)
    await enforce(maker, dry_run=False, max_change_pct=50)
    again = await enforce(maker, dry_run=False, max_change_pct=50)
    assert (again.to_hide, again.to_unhide) == (0, 0)


def test_cli_exit_code_4_on_cap_and_json_report_otherwise(
    maker: async_sessionmaker[AsyncSession],  # noqa: ARG001
) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["enforce", "--dry-run"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert {"visible_before", "hidden", "unhidden", "skipped", "dry_run"} <= set(report)


def _seed_sync(visible: int, rejected: int) -> None:
    async def _go() -> None:
        engine = make_engine()
        maker = make_sessionmaker(engine)
        async with maker() as db:
            await _fill_visible(db, visible)
            for i in range(rejected):
                await _add(db, f"bad-{i}")
        await engine.dispose()

    asyncio.run(_go())


def test_cli_exits_4_when_the_cap_blocks_and_applies_with_a_higher_cap(
    maker: async_sessionmaker[AsyncSession],  # noqa: ARG001
) -> None:
    _seed_sync(visible=20, rejected=15)
    runner = CliRunner()
    blocked = runner.invoke(app, ["enforce"])
    assert blocked.exit_code == 4
    assert "cambio masivo bloqueado" in blocked.output
    applied = runner.invoke(app, ["enforce", "--max-change-pct", "100"])
    assert applied.exit_code == 0, applied.output
    report = json.loads(applied.stdout.strip().splitlines()[-1])
    assert (report["hidden"], report["visible_before"], report["visible_after"]) == (15, 35, 20)


async def test_review_from_the_llm_is_hidden_but_not_curated_nor_rule_only_reviews(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await _fill_visible(db_session, 20)
    await _add(db_session, "unsure-llm", state="review", source="llm")
    await _add(db_session, "unsure-llm-cur", state="review", source="llm", curated=True)
    await _add(db_session, "unsure-rule", state="review", source="rule")
    result = await enforce(maker, dry_run=False, max_change_pct=50)
    assert (result.to_hide, result.to_hide_review) == (1, 1)
    assert await _row(db_session, "unsure-llm") == (True, "classifier")
    assert await _row(db_session, "unsure-llm-cur") == (False, None)
    assert await _row(db_session, "unsure-rule") == (False, None)
    # idempotente: una segunda pasada no cambia nada
    again = await enforce(maker, dry_run=False, max_change_pct=50)
    assert (again.to_hide, again.to_unhide) == (0, 0)


async def test_hidden_review_comes_back_when_a_new_verdict_accepts_it(
    maker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    await _fill_visible(db_session, 20)
    await _add(db_session, "unsure", state="review", source="llm")
    await enforce(maker, dry_run=False, max_change_pct=50)
    assert await _row(db_session, "unsure") == (True, "classifier")
    await db_session.execute(
        text("UPDATE stations SET class_state = 'accepted' WHERE slug = 'unsure'")
    )
    await db_session.commit()
    result = await enforce(maker, dry_run=False, max_change_pct=50)
    assert result.to_unhide == 1
    assert await _row(db_session, "unsure") == (False, None)
