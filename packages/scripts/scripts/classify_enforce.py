"""Aplica el veredicto del clasificador a la visibilidad (ADR 012, Fase 3a).

Una emisora ``rejected`` se oculta con el mismo ``hidden`` que ya respetan todas las consultas
(listas, géneros, tendencias, sitemap, recomendaciones) y queda marcada ``hidden_by =
'classifier'`` para poder reponerla si se reclasifica. Nunca se toca lo oculto por otra vía
(``hidden_by`` NULL: spam, decisión manual) ni las decisiones ``manual``.

Las emisoras en ``review`` también se ocultan cuando el segundo clasificador ya las miró y no
alcanzó confianza para aceptarlas (``class_source = 'llm'``) y no son curadas: ante la duda no
puntúan como electrónica. Se reponen solas si una reevaluación posterior las acepta. Las
``review`` que solo pasaron por las reglas esperan al modelo y siguen visibles.

Defensas, en orden:

- Antigüedad: solo se actúa sobre veredictos de al menos ``min_age_hours`` (por defecto 24 h):
  un cambio puntual de opinión no oculta nada de un día para otro.
- Curadas: una emisora ``curated`` solo se oculta con veredicto del segundo clasificador (que ya
  vio su web y sus temas), nunca solo por las reglas. ``curated`` no garantiza que sea
  electrónica (la marca ``auto-curate-top`` por calidad), pero tampoco se ignora.
- Tope: si una ejecución quiere ocultar más de ``max_change_pct`` % del catálogo visible (mínimo
  ``MIN_CAP_ABS`` emisoras) no aplica nada y falla; la defensa contra una regla, una versión del
  modelo o un error de datos que se desmadre. Reponer no tiene tope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

DEFAULT_MAX_CHANGE_PCT = 5.0
DEFAULT_MIN_AGE_HOURS = 24
MIN_CAP_ABS = 10


class EnforceCapExceededError(Exception):
    def __init__(self, to_hide: int, visible: int, pct: float, limit_pct: float) -> None:
        self.to_hide = to_hide
        self.visible = visible
        self.pct = pct
        self.limit_pct = limit_pct
        super().__init__(
            f"cambio masivo bloqueado: se ocultarían {to_hide} emisoras "
            f"({pct:.1f} % de {visible} visibles) > tope {limit_pct:g} %",
        )


@dataclass
class EnforceResult:
    dry_run: bool
    visible_before: int = 0
    to_hide: int = 0
    to_unhide: int = 0
    to_hide_review: int = 0
    skipped: dict[str, int] = field(default_factory=dict)
    hidden_examples: list[str] = field(default_factory=list)

    @property
    def visible_after(self) -> int:
        return self.visible_before - self.to_hide + self.to_unhide

    def as_dict(self) -> dict[str, object]:
        return {
            "dry_run": self.dry_run,
            "visible_before": self.visible_before,
            "visible_after": self.visible_after,
            "hidden": self.to_hide,
            "hidden_review": self.to_hide_review,
            "unhidden": self.to_unhide,
            "skipped": self.skipped,
            "hidden_examples": self.hidden_examples,
        }


async def _count_visible(session: AsyncSession) -> int:
    return int(
        (
            await session.execute(
                text("SELECT count(*) FROM stations WHERE status = 'active' AND NOT hidden"),
            )
        ).scalar_one(),
    )


async def enforce(
    maker: async_sessionmaker[AsyncSession],
    *,
    dry_run: bool,
    max_change_pct: float = DEFAULT_MAX_CHANGE_PCT,
    min_age_hours: int = DEFAULT_MIN_AGE_HOURS,
) -> EnforceResult:
    result = EnforceResult(dry_run=dry_run)
    cutoff = datetime.now(tz=UTC) - timedelta(hours=min_age_hours)
    async with maker() as session:
        result.visible_before = await _count_visible(session)

        rejected = (
            await session.execute(
                text(
                    "SELECT id, slug, class_source, curated, classified_at, class_state "
                    "FROM stations "
                    "WHERE ((class_state = 'rejected' AND class_source IN ('rule', 'llm')) "
                    "OR (class_state = 'review' AND class_source = 'llm' AND NOT curated)) "
                    "AND status = 'active' AND NOT hidden ORDER BY slug",
                ),
            )
        ).all()
        hide_ids: list[object] = []
        skipped = {"curated_rule_only": 0, "too_recent": 0}
        for sid, slug, source, curated, classified_at, state in rejected:
            if curated and source != "llm":
                skipped["curated_rule_only"] += 1
            elif classified_at is None or classified_at > cutoff:
                skipped["too_recent"] += 1
            else:
                hide_ids.append(sid)
                if state == "review":
                    result.to_hide_review += 1
                if len(result.hidden_examples) < 10:  # noqa: PLR2004
                    result.hidden_examples.append(slug)
        result.skipped = skipped
        result.to_hide = len(hide_ids)

        unhide_ids = [
            r[0]
            for r in (
                await session.execute(
                    text(
                        "SELECT id FROM stations WHERE hidden AND hidden_by = 'classifier' "
                        "AND class_state IS DISTINCT FROM 'rejected' "
                        "AND NOT (class_state = 'review' AND class_source = 'llm' "
                        "AND NOT curated)",
                    ),
                )
            ).all()
        ]
        result.to_unhide = len(unhide_ids)

        cap = max(MIN_CAP_ABS, result.visible_before * max_change_pct / 100)
        if result.to_hide > cap:
            pct = result.to_hide / result.visible_before * 100 if result.visible_before else 100.0
            raise EnforceCapExceededError(
                result.to_hide, result.visible_before, pct, max_change_pct
            )

        if not dry_run:
            if hide_ids:
                await session.execute(
                    text(
                        "UPDATE stations SET hidden = true, hidden_by = 'classifier' "
                        "WHERE id = ANY(:ids) AND NOT hidden",
                    ),
                    {"ids": hide_ids},
                )
            if unhide_ids:
                await session.execute(
                    text(
                        "UPDATE stations SET hidden = false, hidden_by = NULL "
                        "WHERE id = ANY(:ids) AND hidden_by = 'classifier'",
                    ),
                    {"ids": unhide_ids},
                )
            await session.commit()
    return result
