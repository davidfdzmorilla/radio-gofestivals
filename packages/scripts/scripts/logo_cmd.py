"""fetch-logos · CLI command (ADR 011).

Para cada emisora activa busca un logo y guarda dos copias WebP propias en `station_logos`
(`stations.logo_hash` copia el hash para los listados). Escalera de fuentes:

1. El `favicon` de Radio-Browser (`stations.favicon_url`).
2. Si no sirve (no existe, 404, demasiado pequeño, invisible sobre el recuadro claro): el
   icono de marca de la web de la emisora (`homepage_url`): apple-touch-icon o
   `<link rel=icon>`, descartando redes sociales y plataformas genéricas.

Pensado para correr cada noche tras `rb_sync`; es idempotente: solo toca lo que toca
(nuevo, URL cambiada, reintento con backoff o refresco mensual).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx
import typer
from sqlalchemy import text

from scripts.db import make_engine, make_sessionmaker
from scripts.logging import get_logger
from scripts.logo_discovery import (
    extract_icon_candidates,
    fetch_html,
    is_eligible_homepage,
    registrable_domain,
)
from scripts.logo_fetch import LogoFetchError, LogoRejectedError, ProcessedLogo, fetch_logo
from scripts.url_guard import guard_request

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

log = get_logger("fetch_logos")
app = typer.Typer(help="radio.gofestivals · descarga y procesa los logos de las emisoras")

# Reintentos tras un fallo transitorio: 1, 3, 7, 14 y luego 30 días.
BACKOFF_DAYS = (1, 3, 7, 14, 30)
REFRESH_DAYS = 30
# Hay hosts (i.ibb.co, postimg…) con decenas de logos nuestros: no se les abre una
# avalancha de conexiones. Cuenta toda petición: favicon, web e icono.
PER_HOST_CONCURRENCY = 2
MAX_ERROR_LENGTH = 300
KIND_FAVICON = "favicon"
KIND_HOMEPAGE = "homepage"
# Una misma imagen en tantos sitios distintos no es de una emisora: es el icono por defecto de
# un software de gestión de radio (AzuraCast…) o de una plataforma. Medido en producción: una
# nota musical azul repetida en 8 emisoras de hosts sin relación.
GENERIC_ICON_MIN_SITES = 3


@dataclass(frozen=True)
class Candidate:
    station_id: uuid.UUID
    slug: str
    favicon_url: str | None
    homepage_url: str | None
    previous_attempts: int
    # Las URLs de entrada no han cambiado desde el último intento (para contar reintentos).
    inputs_unchanged: bool
    # Hay un logo válido cuyo origen sigue vigente: un refresco fallido no debe perderlo.
    keep_previous: bool

    @property
    def source_url(self) -> str:
        """URL a registrar cuando no hay logo: la que se intentó primero."""
        return self.favicon_url or self.homepage_url or ""


@dataclass
class Stats:
    ok: int = 0
    failed: int = 0
    rejected: int = 0
    via_homepage: int = 0
    purged: int = 0


@dataclass(frozen=True)
class Resolution:
    outcome: str  # "ok" | "failed" | "rejected"
    logo: ProcessedLogo | None = None
    kind: str | None = None
    source_url: str | None = None
    error: str = ""


class Limiter:
    """Concurrencia global y por host, sobre cada petición de red."""

    def __init__(self, concurrency: int) -> None:
        self._global = asyncio.Semaphore(concurrency)
        self._hosts: defaultdict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(PER_HOST_CONCURRENCY),
        )

    @asynccontextmanager
    async def slot(self, url: str) -> AsyncIterator[None]:
        host = urlparse(url).hostname or ""
        async with self._global, self._hosts[host]:
            yield


def backoff(attempts: int) -> timedelta:
    """Espera antes del siguiente intento tras `attempts` fallos seguidos (1 = el primero)."""
    return timedelta(days=BACKOFF_DAYS[min(max(attempts, 1), len(BACKOFF_DAYS)) - 1])


def build_client() -> httpx.AsyncClient:
    """Cliente con el guard SSRF en cada petición y redirección (ADR 008)."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=10.0),
        follow_redirects=True,
        max_redirects=3,
        limits=httpx.Limits(max_connections=20),
        event_hooks={"request": [guard_request]},
    )


async def select_candidates(
    session: AsyncSession,
    *,
    limit: int,
    slug: str | None = None,
) -> list[Candidate]:
    # Con `slug` se ignoran los plazos: sirve para forzar una emisora concreta.
    due = (
        ""
        if slug
        else """
        AND (
            l.station_id IS NULL
            OR l.favicon_seen IS DISTINCT FROM s.favicon_url
            -- sin logo y la web es otra (o nunca se probó la web): se vuelve a intentar
            OR (l.status <> 'ok' AND l.homepage_seen IS DISTINCT FROM s.homepage_url)
            OR (l.status = 'failed' AND l.next_retry_at <= now())
            OR (
                l.status = 'ok'
                AND l.fetched_at < now() - make_interval(days => :refresh_days)
                AND COALESCE(l.next_retry_at, now()) <= now()
            )
        )"""
    )
    only = "AND s.slug = :slug" if slug else ""
    params: dict[str, object] = {"limit": limit}
    if slug:
        params["slug"] = slug
    else:
        params["refresh_days"] = REFRESH_DAYS
    rows = (
        await session.execute(
            text(
                f"""
                SELECT s.id, s.slug, s.favicon_url, s.homepage_url,
                       COALESCE(l.attempts, 0),
                       COALESCE(
                           l.favicon_seen IS NOT DISTINCT FROM s.favicon_url
                           AND l.homepage_seen IS NOT DISTINCT FROM s.homepage_url,
                           false
                       ),
                       COALESCE(
                           l.status = 'ok' AND (
                               (l.source_kind = 'favicon'
                                AND l.favicon_seen IS NOT DISTINCT FROM s.favicon_url)
                               OR (l.source_kind = 'homepage'
                                   AND l.favicon_seen IS NOT DISTINCT FROM s.favicon_url
                                   AND l.homepage_seen IS NOT DISTINCT FROM s.homepage_url)
                           ),
                           false
                       )
                FROM stations s
                LEFT JOIN station_logos l ON l.station_id = s.id
                WHERE (s.favicon_url IS NOT NULL OR s.homepage_url IS NOT NULL)
                  AND s.status = 'active'
                  AND s.hidden = false
                  {only}
                  {due}
                ORDER BY (l.station_id IS NOT NULL), s.quality_score DESC, s.id
                LIMIT :limit
                """,  # noqa: S608
            ),
            params,
        )
    ).all()
    return [
        Candidate(
            station_id=uuid.UUID(str(r[0])),
            slug=str(r[1]),
            favicon_url=None if r[2] is None else str(r[2]),
            homepage_url=None if r[3] is None else str(r[3]),
            previous_attempts=int(r[4]),
            inputs_unchanged=bool(r[5]),
            keep_previous=bool(r[6]),
        )
        for r in rows
    ]


async def _save_ok(session: AsyncSession, cand: Candidate, res: Resolution) -> None:
    assert res.logo is not None  # noqa: S101 — contrato interno de _process_one
    await session.execute(
        text(
            """
            INSERT INTO station_logos
                (station_id, source_url, source_kind, favicon_seen, homepage_seen, status,
                 content_hash, data_sm, data_lg, attempts, last_error, checked_at,
                 fetched_at, next_retry_at, updated_at)
            VALUES
                (:id, :url, :kind, :fav, :home, 'ok', :hash, :sm, :lg, 0, NULL, now(),
                 now(), NULL, now())
            ON CONFLICT (station_id) DO UPDATE SET
                source_url = EXCLUDED.source_url, source_kind = EXCLUDED.source_kind,
                favicon_seen = EXCLUDED.favicon_seen, homepage_seen = EXCLUDED.homepage_seen,
                status = 'ok', content_hash = EXCLUDED.content_hash,
                data_sm = EXCLUDED.data_sm, data_lg = EXCLUDED.data_lg,
                attempts = 0, last_error = NULL, checked_at = now(), fetched_at = now(),
                next_retry_at = NULL, updated_at = now()
            """,
        ),
        {
            "id": str(cand.station_id),
            "url": res.source_url,
            "kind": res.kind,
            "fav": cand.favicon_url,
            "home": cand.homepage_url,
            "hash": res.logo.content_hash,
            "sm": res.logo.sm,
            "lg": res.logo.lg,
        },
    )
    await session.execute(
        text("UPDATE stations SET logo_hash = :hash WHERE id = :id"),
        {"id": str(cand.station_id), "hash": res.logo.content_hash},
    )


async def _save_failed(session: AsyncSession, cand: Candidate, error: str) -> None:
    attempts = cand.previous_attempts + 1 if cand.inputs_unchanged else 1
    # Si el logo anterior sigue siendo válido (mismas URLs de origen), un refresco fallido
    # lo conserva con su origen; si cambió algún origen, el logo anterior ya no corresponde.
    await session.execute(
        text(
            """
            INSERT INTO station_logos
                (station_id, source_url, favicon_seen, homepage_seen, status, attempts,
                 last_error, checked_at, next_retry_at, updated_at)
            VALUES
                (:id, :url, :fav, :home, 'failed', :attempts, :err, now(), now() + :delay, now())
            ON CONFLICT (station_id) DO UPDATE SET
                status = CASE WHEN :keep THEN 'ok' ELSE 'failed' END,
                source_url = CASE WHEN :keep THEN station_logos.source_url
                                  ELSE EXCLUDED.source_url END,
                source_kind = CASE WHEN :keep THEN station_logos.source_kind END,
                content_hash = CASE WHEN :keep THEN station_logos.content_hash END,
                data_sm = CASE WHEN :keep THEN station_logos.data_sm END,
                data_lg = CASE WHEN :keep THEN station_logos.data_lg END,
                favicon_seen = EXCLUDED.favicon_seen, homepage_seen = EXCLUDED.homepage_seen,
                attempts = EXCLUDED.attempts, last_error = EXCLUDED.last_error,
                checked_at = now(), next_retry_at = EXCLUDED.next_retry_at, updated_at = now()
            """,
        ),
        {
            "id": str(cand.station_id),
            "url": cand.source_url,
            "fav": cand.favicon_url,
            "home": cand.homepage_url,
            "attempts": attempts,
            "err": error[:MAX_ERROR_LENGTH],
            "delay": backoff(attempts),
            "keep": cand.keep_previous,
        },
    )
    if not cand.keep_previous:
        await session.execute(
            text("UPDATE stations SET logo_hash = NULL WHERE id = :id"),
            {"id": str(cand.station_id)},
        )


async def _save_rejected(session: AsyncSession, cand: Candidate, error: str) -> None:
    await session.execute(
        text(
            """
            INSERT INTO station_logos
                (station_id, source_url, favicon_seen, homepage_seen, status, attempts,
                 last_error, checked_at, updated_at)
            VALUES (:id, :url, :fav, :home, 'rejected', 1, :err, now(), now())
            ON CONFLICT (station_id) DO UPDATE SET
                source_url = EXCLUDED.source_url, source_kind = NULL,
                favicon_seen = EXCLUDED.favicon_seen, homepage_seen = EXCLUDED.homepage_seen,
                status = 'rejected', content_hash = NULL, data_sm = NULL, data_lg = NULL,
                attempts = 1, last_error = EXCLUDED.last_error, checked_at = now(),
                next_retry_at = NULL, updated_at = now()
            """,
        ),
        {
            "id": str(cand.station_id),
            "url": cand.source_url,
            "fav": cand.favicon_url,
            "home": cand.homepage_url,
            "err": error[:MAX_ERROR_LENGTH],
        },
    )
    await session.execute(
        text("UPDATE stations SET logo_hash = NULL WHERE id = :id"),
        {"id": str(cand.station_id)},
    )


async def find_unwanted_homepage_logos(session: AsyncSession) -> dict[uuid.UUID, str]:
    """Logos obtenidos de la web que ya no deben servirse, con el motivo.

    1. La web ahora está en la lista de dominios denegados (la lista crece con el tiempo).
    2. La misma imagen sale en `GENERIC_ICON_MIN_SITES` o más sitios distintos: icono genérico.
    Los logos que vienen del favicon de Radio-Browser no se tocan.
    """
    rows = (
        await session.execute(
            text(
                """
                SELECT station_id, content_hash, homepage_seen
                FROM station_logos
                WHERE status = 'ok' AND source_kind = 'homepage' AND content_hash IS NOT NULL
                """,
            ),
        )
    ).all()
    unwanted: dict[uuid.UUID, str] = {}
    sites: defaultdict[str, set[str]] = defaultdict(set)
    for sid, content_hash, homepage in rows:
        if not is_eligible_homepage(homepage):
            unwanted[uuid.UUID(str(sid))] = "homepage is now a denied domain"
        sites[str(content_hash)].add(registrable_domain(str(homepage or "")))
    generic = {h for h, domains in sites.items() if len(domains) >= GENERIC_ICON_MIN_SITES}
    for sid, content_hash, _ in rows:
        if str(content_hash) in generic:
            n = len(sites[str(content_hash)])
            unwanted.setdefault(uuid.UUID(str(sid)), f"generic icon shared by {n} different sites")
    return unwanted


async def purge_unwanted_logos(
    maker: async_sessionmaker[AsyncSession],
    *,
    dry_run: bool = False,
) -> int:
    """Pasa a `rejected` los logos de la web que no deben servirse. Devuelve cuántos."""
    async with maker() as session:
        unwanted = await find_unwanted_homepage_logos(session)
        if unwanted and not dry_run:
            for sid, why in unwanted.items():
                await session.execute(
                    text(
                        """
                        UPDATE station_logos SET
                            status = 'rejected', source_kind = NULL, content_hash = NULL,
                            data_sm = NULL, data_lg = NULL, last_error = :why,
                            next_retry_at = NULL, updated_at = now()
                        WHERE station_id = :id
                        """,
                    ),
                    {"id": str(sid), "why": why},
                )
                await session.execute(
                    text("UPDATE stations SET logo_hash = NULL WHERE id = :id"),
                    {"id": str(sid)},
                )
            await session.commit()
    return len(unwanted)


async def _try_logo(
    client: httpx.AsyncClient,
    limiter: Limiter,
    url: str,
) -> ProcessedLogo:
    async with limiter.slot(url):
        return await fetch_logo(client, url)


async def _homepage_icon(
    client: httpx.AsyncClient,
    limiter: Limiter,
    homepage: str,
    errors: list[str],
) -> tuple[ProcessedLogo, str] | None:
    """Icono de marca de la web, o None. Un fallo definitivo se anota; uno transitorio lanza."""
    async with limiter.slot(homepage):
        final_url, html = await fetch_html(client, homepage)
    for icon in extract_icon_candidates(html, final_url):
        try:
            return await _try_logo(client, limiter, icon.url), icon.url
        except LogoRejectedError as exc:
            errors.append(f"{icon.kind}: {exc}")
        except LogoFetchError as exc:
            errors.append(f"{icon.kind}: {exc}")
    return None


async def resolve_logo(
    client: httpx.AsyncClient,
    limiter: Limiter,
    cand: Candidate,
) -> Resolution:
    """Escalera favicon → icono de la web. `failed` = vale la pena reintentar; `rejected` = no."""
    errors: list[str] = []
    retry = False  # algo pudo fallar por causas pasajeras

    if cand.favicon_url:
        try:
            logo = await _try_logo(client, limiter, cand.favicon_url)
        except LogoRejectedError as exc:
            errors.append(f"favicon: {exc}")
        except LogoFetchError as exc:
            errors.append(f"favicon: {exc}")
            retry = True
        else:
            return Resolution("ok", logo, KIND_FAVICON, cand.favicon_url)

    if cand.homepage_url:
        if not is_eligible_homepage(cand.homepage_url):
            errors.append("homepage: social network or generic platform")
        else:
            try:
                found = await _homepage_icon(client, limiter, cand.homepage_url, errors)
            except LogoRejectedError as exc:
                errors.append(f"homepage: {exc}")
            except LogoFetchError as exc:
                errors.append(str(exc))
                retry = True
            else:
                if found is not None:
                    return Resolution("ok", found[0], KIND_HOMEPAGE, found[1])
                # La web respondió pero no tiene un icono utilizable: puede añadirlo.
                retry = True

    return Resolution("failed" if retry else "rejected", error="; ".join(errors))


async def _process_one(
    client: httpx.AsyncClient,
    limiter: Limiter,
    maker: async_sessionmaker[AsyncSession],
    cand: Candidate,
    stats: Stats,
    *,
    dry_run: bool,
) -> None:
    try:
        res = await resolve_logo(client, limiter, cand)
    except Exception as exc:  # noqa: BLE001 — un logo roto nunca debe tumbar el job
        res = Resolution("failed", error=f"unexpected {type(exc).__name__}: {exc}")
    log.debug(
        "logo_result", slug=cand.slug, outcome=res.outcome, kind=res.kind, error=res.error or None
    )
    if res.outcome == "ok":
        stats.ok += 1
        stats.via_homepage += res.kind == KIND_HOMEPAGE
    elif res.outcome == "rejected":
        stats.rejected += 1
    else:
        stats.failed += 1
    if dry_run:
        return
    async with maker() as session:
        if res.outcome == "ok":
            await _save_ok(session, cand, res)
        elif res.outcome == "rejected":
            await _save_rejected(session, cand, res.error)
        else:
            await _save_failed(session, cand, res.error)
        await session.commit()


async def process_candidates(
    maker: async_sessionmaker[AsyncSession],
    client: httpx.AsyncClient,
    candidates: list[Candidate],
    *,
    concurrency: int = 8,
    dry_run: bool = False,
) -> Stats:
    stats = Stats()
    limiter = Limiter(concurrency)
    await asyncio.gather(
        *(_process_one(client, limiter, maker, c, stats, dry_run=dry_run) for c in candidates),
    )
    return stats


@app.command()
def fetch_logos(
    dry_run: bool = typer.Option(
        default=False,
        help="Descarga y procesa, pero no escribe en la base de datos.",
    ),
    limit: int = typer.Option(
        default=3000,
        help="Máximo de emisoras a procesar en esta pasada.",
    ),
    concurrency: int = typer.Option(
        default=8,
        help="Descargas simultáneas (máx. 2 por host).",
    ),
    station: str | None = typer.Option(
        default=None,
        help="Slug concreto: ignora los plazos y vuelve a descargar su logo.",
    ),
) -> None:
    """Descarga y procesa los logos pendientes de las emisoras activas."""

    async def _main() -> None:
        engine = make_engine()
        maker = make_sessionmaker(engine)
        started = time.monotonic()
        try:
            async with maker() as session:
                candidates = await select_candidates(session, limit=limit, slug=station)
            log.info("fetch_logos_start", candidates=len(candidates), dry_run=dry_run)
            async with build_client() as client:
                stats = await process_candidates(
                    maker,
                    client,
                    candidates,
                    concurrency=concurrency,
                    dry_run=dry_run,
                )
            # Tras descargar: el logo nuevo puede ser un icono genérico repetido, y la lista de
            # dominios denegados puede haber crecido desde que se guardaron los antiguos.
            stats.purged = await purge_unwanted_logos(maker, dry_run=dry_run)
            log.info(
                "fetch_logos_done",
                dry_run=dry_run,
                candidates=len(candidates),
                ok=stats.ok,
                failed=stats.failed,
                rejected=stats.rejected,
                via_homepage=stats.via_homepage,
                purged=stats.purged,
                seconds=round(time.monotonic() - started, 1),
            )
        finally:
            await engine.dispose()

    asyncio.run(_main())
