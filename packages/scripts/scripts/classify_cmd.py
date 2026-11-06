"""classify-stations · CLI de la clasificación "¿es electrónica?" (Fase 1, modo sombra).

Dos pasos, ambos idempotentes y sin efecto sobre lo que ve el usuario:

- ``backfill-tags``: recoge de Radio-Browser, por `rb_uuid`, los tags crudos de las emisoras
  que aún no los tienen (`rb_tags IS NULL`). ``rb_sync`` los guarda ya al importar.
- ``run``: calcula el veredicto de reglas de cada emisora con tags y lo guarda en
  `electronic_score` / `class_state` / `class_reason`; imprime un informe por estado.

Nada lee esas columnas para ocultar emisoras: es medición. Las decisiones manuales
(`class_source = 'manual'`) no se pisan.
"""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import typer
from sqlalchemy import text

from scripts.db import make_engine, make_sessionmaker
from scripts.logging import get_logger
from scripts.rb_client import RadioBrowserClient
from scripts.rb_sync import parse_tags
from scripts.station_classifier import classify, normalize_tags

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

log = get_logger("classify_stations")
app = typer.Typer(help="radio.gofestivals · clasificación de emisoras (modo sombra)")

BACKFILL_BATCH = 50
SAMPLE_PER_STATE = 8


async def backfill_tags(
    maker: async_sessionmaker[AsyncSession],
    client: RadioBrowserClient,
    *,
    dry_run: bool,
    limit: int | None,
) -> dict[str, int]:
    stats = {"pending": 0, "fetched": 0, "updated": 0, "missing": 0}
    async with maker() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id, rb_uuid::text FROM stations "
                    "WHERE rb_uuid IS NOT NULL AND rb_tags IS NULL ORDER BY created_at",
                ),
            )
        ).all()
        if limit is not None:
            rows = rows[:limit]
        stats["pending"] = len(rows)
        for i in range(0, len(rows), BACKFILL_BATCH):
            batch = rows[i : i + BACKFILL_BATCH]
            by_uuid = {str(r[1]): r[0] for r in batch}
            items = await client.fetch_stations_by_uuids(list(by_uuid))
            stats["fetched"] += len(items)
            seen: set[str] = set()
            for item in items:
                rb_uuid = str(item.get("stationuuid") or "")
                station_id = by_uuid.get(rb_uuid)
                if station_id is None:
                    continue
                seen.add(rb_uuid)
                tags = normalize_tags(parse_tags(item.get("tags")))
                if not dry_run:
                    await session.execute(
                        text("UPDATE stations SET rb_tags = :tags WHERE id = :id"),
                        {"tags": tags, "id": station_id},
                    )
                stats["updated"] += 1
            # Ya no existen en Radio-Browser: sin evidencia que recoger, se deja NULL.
            stats["missing"] += len(by_uuid) - len(seen)
            if not dry_run:
                await session.commit()
            log.info("backfill_progress", done=min(i + BACKFILL_BATCH, len(rows)), total=len(rows))
    return stats


async def run_classification(
    maker: async_sessionmaker[AsyncSession],
    *,
    dry_run: bool,
) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    counts: Counter[str] = Counter()
    samples: dict[str, list[dict[str, Any]]] = {"accepted": [], "review": [], "rejected": []}
    curated_conflicts: list[dict[str, Any]] = []
    async with maker() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id, slug, name, rb_tags, curated "
                    "FROM stations "
                    "WHERE rb_tags IS NOT NULL "
                    "AND COALESCE(class_source, 'rule') <> 'manual' "
                    "ORDER BY slug",
                ),
            )
        ).all()
        for station_id, slug, name, rb_tags, curated in rows:
            verdict = classify(list(rb_tags), name)
            counts[verdict.state] += 1
            entry = {
                "slug": slug,
                "name": name,
                "score": verdict.score,
                "reason": verdict.reason,
                "curated": curated,
            }
            if len(samples[verdict.state]) < SAMPLE_PER_STATE:
                samples[verdict.state].append(entry)
            if curated and verdict.state == "rejected":
                curated_conflicts.append(entry)
            if not dry_run:
                await session.execute(
                    text(
                        "UPDATE stations SET electronic_score = :score, class_state = :state, "
                        "class_reason = :reason, class_source = 'rule', classified_at = :now "
                        "WHERE id = :id",
                    ),
                    {
                        "score": verdict.score,
                        "state": verdict.state,
                        "reason": verdict.reason,
                        "now": now,
                        "id": station_id,
                    },
                )
        if not dry_run:
            await session.commit()
    return {
        "dry_run": dry_run,
        "classified": sum(counts.values()),
        "by_state": dict(counts),
        "curated_rejected": curated_conflicts,
        "samples": samples,
    }


@app.command("backfill-tags")
def cmd_backfill_tags(
    dry_run: bool = typer.Option(False, "--dry-run", help="No escribe en la base de datos"),  # noqa: FBT001,FBT002
    limit: int | None = typer.Option(None, "--limit", help="Máximo de emisoras a procesar"),
) -> None:
    engine = make_engine()
    maker = make_sessionmaker(engine)

    async def _main() -> dict[str, int]:
        try:
            async with RadioBrowserClient() as client:
                return await backfill_tags(maker, client, dry_run=dry_run, limit=limit)
        finally:
            await engine.dispose()

    stats = asyncio.run(_main())
    log.info("backfill_done", dry_run=dry_run, **stats)


@app.command("run")
def cmd_run(
    dry_run: bool = typer.Option(False, "--dry-run", help="Solo informe; no escribe"),  # noqa: FBT001,FBT002
) -> None:
    engine = make_engine()
    maker = make_sessionmaker(engine)

    async def _main() -> dict[str, Any]:
        try:
            return await run_classification(maker, dry_run=dry_run)
        finally:
            await engine.dispose()

    report = asyncio.run(_main())
    typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
