# CLAUDE.md · radio.gofestivals

Este archivo es leído por Claude Code al inicio de cada sesión en este repo.
Contiene el contexto mínimo necesario para trabajar en el proyecto sin tener
que releer todo el documento técnico cada vez.

---

## 1 · Qué es este proyecto

**radio.gofestivals** es una plataforma de radio online curada exclusivamente
para música electrónica, conectada al ecosistema gofestivals (portales
`gofestivals.eu` internacional y `gofestivals.es` España).

**Objetivo**: catálogo filtrable por género, metadata en vivo (now-playing)
y vínculo con festivales del ecosistema. No es clon de radio.garden — el
descubrimiento es por listas y filtros, no por globo 3D.

**Fuente de datos**: Radio-Browser API (sync nocturno) + curación manual
editorial. La taxonomía de géneros es **propia**, no copiamos los tags
sucios de Radio-Browser.

**Documentación completa**: `docs/technical-spec.pdf` (21 páginas).
Consultar para cualquier decisión arquitectónica no cubierta aquí.

---

## 2 · Stack

| Capa      | Tecnología                     | Versión   |
|-----------|--------------------------------|-----------|
| Frontend  | Next.js (App Router)           | 15.x      |
| UI        | Tailwind + shadcn/ui           | última    |
| Backend   | FastAPI                        | 0.115+    |
| Lenguaje  | Python                         | 3.12      |
| ORM       | SQLAlchemy 2.x + Alembic       | 2.x       |
| DB        | PostgreSQL + PostGIS + pg_trgm | 16 / 3.4  |
| Cache     | Redis                          | 7         |
| HTTP (py) | httpx async                    | última    |
| Worker    | asyncio (ICY metadata)         | stdlib    |
| Proxy     | Traefik                        | 3.x       |
| Host      | Hetzner CX22                   | —         |
| CI/CD     | GitLab CI                      | self-host |
| Package mgr (py) | uv                      | última    |
| Package mgr (js) | pnpm                    | última    |

---

## 3 · Estructura del repo

```
radio.gofestivals/
├── CLAUDE.md              ← este archivo
├── README.md
├── docker-compose.yml     ← stack local completo
├── .env.example
├── docs/
│   ├── technical-spec.pdf
│   └── adr/               ← decisiones arquitectónicas
├── apps/
│   ├── api/               ← FastAPI backend
│   │   ├── CLAUDE.md      ← contexto específico del backend
│   │   ├── pyproject.toml
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── api/v1/    ← routers por recurso
│   │   │   ├── services/  ← lógica de dominio
│   │   │   ├── repos/     ← acceso a DB
│   │   │   ├── models/    ← SQLAlchemy models
│   │   │   ├── schemas/   ← Pydantic schemas
│   │   │   └── core/      ← config, logging, db, redis
│   │   ├── alembic/       ← migraciones
│   │   └── tests/
│   └── web/               ← Next.js frontend
│       ├── CLAUDE.md      ← contexto específico del frontend
│       ├── package.json
│       ├── src/
│       │   ├── app/       ← App Router
│       │   ├── components/
│       │   ├── lib/       ← api client, utils
│       │   └── hooks/
│       └── tests/
├── packages/
│   ├── icy-worker/        ← worker Python de now-playing
│   └── scripts/           ← rb_sync.py, taxonomy_mapper.py, maintenance
└── infra/
    ├── traefik/
    ├── prometheus/
    └── sql/               ← schema.sql inicial, seeds
```

---

## 4 · Reglas del agente (NO NEGOCIABLES)

Estas reglas están en orden de importancia:

1. **No inventar APIs externas**. Radio-Browser, PostGIS, ICY metadata: si
   no estás 100% seguro de la firma, lee docs oficiales o busca un ejemplo
   real en el repo antes de escribir. Prohibido asumir endpoints, parámetros
   o estructuras de respuesta.

2. **No merge sin tests pasando**. Cualquier cambio en `api/`, `packages/` o
   schema de DB requiere test de integración. E2E (Playwright) solo para
   flujos críticos del frontend.

3. **Migraciones atómicas con Alembic**. Cada cambio de schema → una
   `alembic revision --autogenerate`. Revisar el SQL generado antes de
   commitear. Nunca `ALTER TABLE` manual. Cuando sea posible, migración
   reversible (`downgrade` funcional).

   **Nunca editar `infra/sql/schema.sql` retroactivamente** (ver ADR 001).
   Ese archivo es el snapshot inicial cargado por la migración 0001 y por
   `docker-entrypoint-initdb.d`; modificarlo crea divergencia silenciosa
   con las DBs ya desplegadas. Cualquier cambio de schema posterior a
   0001 va exclusivamente por `alembic revision`. La única excepción
   legítima es un fix de erratas que NO cambian DDL ejecutable
   (comentarios, formato, typos en texto de seeds); en ese caso el commit
   debe llevar el tag `[schema-intended]` en el subject para que el hook
   de pre-commit lo permita.

4. **Commits pequeños, prefijo de scope**. Un cambio lógico por commit.
   Subject < 72 chars, imperativo. Prefijos:
   - `api:` backend FastAPI
   - `web:` frontend Next.js
   - `worker:` icy-worker
   - `scripts:` rb_sync, maintenance
   - `db:` migraciones / schema
   - `infra:` docker, traefik, CI
   - `docs:` documentación

5. **Cero secrets en código**. Todo por `.env`. Si falta una variable, el
   servicio debe fallar ruidoso al arranque (`ValueError` explícito en
   `core/config.py`). Ni siquiera placeholders "solo dev".

6. **Decisiones no triviales → ADR**. Archivo en `docs/adr/NNN-titulo.md`
   con: Contexto (2-3 párrafos), Decisión (1 párrafo), Consecuencias
   (positivas y negativas, honestas).

7. **No E2E → no submit** (regla heredada de metodología NyxSec). Si no has
   verificado end-to-end que el cambio funciona (no solo que los tests
   unitarios pasan), no está terminado.

8. **`@pytest.mark.xfail` NO es una solución de primera línea**. Un test
   que falla casi siempre revela un bug real, no un capricho del entorno.
   Antes de aplicar xfail, es obligatorio:
   - (a) **Diagnosticar causa raíz verificada** (no "suena a timing").
     Añadir logs, reproducir, hipótesis probada.
   - (b) **Documentar condiciones específicas** de la flakyness en el
     `reason=` del decorator (plataforma, timing, dependencias).
   - (c) **Usar `strict=True`** siempre que sea posible para que un
     XPASS inesperado rompa el build (mejor que silenciarse).
   - (d) **Abrir issue o `TODO(nombre, fecha)`** en código para el fix
     futuro, con el hash del commit que introdujo el xfail.

   Antiejemplo: marcar xfail sin diagnosticar y descubrir después que
   el test detectaba un bug de producción (ver commit `9958880`,
   cancellation-safety del publish en el WS handler).

---

## 5 · Comandos frecuentes

### Setup inicial

```bash
cp .env.example .env
docker compose up -d postgres redis
cd apps/api && uv sync
uv run alembic upgrade head
uv run python -m app.scripts.seed_genres
```

### Desarrollo

```bash
# Backend
cd apps/api
uv run uvicorn app.main:app --reload --port 8000

# Frontend
cd apps/web
pnpm install
pnpm dev

# Worker now-playing (solo si se va a probar)
cd packages/icy-worker
uv run python -m icy_worker
```

### Tests

```bash
# Backend todo
cd apps/api && uv run pytest

# Solo unit
uv run pytest tests/unit

# Solo integration (requiere postgres+redis arriba)
uv run pytest tests/integration

# Frontend
cd apps/web && pnpm test

# E2E
pnpm playwright test
```

### Lint / type-check

```bash
cd apps/api
uv run ruff check app
uv run ruff format app
uv run mypy app --strict

cd apps/web
pnpm lint
pnpm typecheck
```

### Sync manual de Radio-Browser

```bash
cd packages/scripts
uv run python rb_sync.py --dry-run       # ver qué pasaría
uv run python rb_sync.py                  # ejecutar de verdad
uv run python rb_sync.py --tag techno     # solo un tag
```

### Migraciones

```bash
cd apps/api
# Crear nueva migración
uv run alembic revision --autogenerate -m "add column foo to stations"
# Aplicar
uv run alembic upgrade head
# Revertir última
uv run alembic downgrade -1
```

---

## 6 · Convenciones de código

### Python (backend + worker)

- **Formato**: `ruff format`, 100 cols, comillas dobles
- **Linter**: `ruff check` con `--select ALL` y excepciones justificadas
- **Tipos**: `mypy --strict`. Toda función pública tipada.
- **Async por defecto** en endpoints y repos. Si algo es sync genuinamente
  bloqueante, usar `anyio.to_thread.run_sync`.
- **Async cancellation safety**. Si hay un `await` dentro del `finally` de
  un handler async (WebSocket, task de larga duración, background job),
  protegerlo con `asyncio.shield(asyncio.ensure_future(op()))`. Sin
  shield, cuando el task outer recibe `CancelledError` (cliente que se
  desconecta, shutdown del server, timeout), el `await` del `finally` se
  re-lanza como `CancelledError` ANTES de ejecutar la operación — y se
  pierde silenciosamente. Referencia: `apps/api/app/api/v1/ws/nowplaying.py`
  en el `finally` del handler publica `icy:release` con `shield` para que
  el worker libere el stream aunque el cliente cierre abruptamente.
- **Imports absolutos**: `from app.services.stations import ...`
- **Config**: `app/core/config.py` con `pydantic-settings`. Todo
  setting leído de env con tipo explícito.
- **Logging**: `structlog`, nivel INFO por defecto, DEBUG solo en dev.
  Mensajes en inglés, keys en snake_case. Nunca `print()` en código de
  producción.
- **Docstrings**: solo donde añaden valor (lógica no obvia, invariantes).
  Código obvio no necesita docstring.
- **Layers**: `api/` llama `services/` llama `repos/`. `api/` NO accede a
  DB directamente. `services/` NO construye SQL directamente.

### TypeScript (frontend)

- **Formato**: Prettier con config del repo
- **Linter**: ESLint con `next/core-web-vitals` + `@typescript-eslint/strict`
- **Componentes**: server components por defecto. `'use client'` solo
  cuando necesario (estado, efectos, handlers).
- **Data fetching**: `fetch` nativo con tag-based caching para ISR.
  No SWR/React Query salvo que un caso concreto lo requiera.
- **Estilos**: solo Tailwind + shadcn. Nada de CSS modules ni
  styled-components.
- **No barrel files** (`index.ts` que reexporta todo). Import directo.

### SQL

- `snake_case` para tablas, columnas, índices, constraints.
- Plural para nombres de tabla (`stations`, no `station`).
- Cada tabla tiene `created_at` y `updated_at` con default `now()`.
- Índices nombrados: `idx_<tabla>_<col(s)>`.
- Foreign keys nombradas: `fk_<tabla_origen>_<tabla_destino>`.
- PKs como `uuid` salvo entidades de alta frecuencia donde `bigserial`
  tiene mejor perf.

---

## 7 · Decisiones arquitectónicas clave (resumen)

Están en `docs/adr/` completas. Aquí el TL;DR:

- **PostGIS `geography(POINT, 4326)`** en lugar de `geometry` porque las
  queries son por distancia en km, no por área. `ST_DWithin` con geography
  da resultados correctos sin conversiones manuales.

- **Taxonomía de géneros propia**, no los tags de Radio-Browser. La tabla
  `genres` tiene árbol jerárquico (`parent_id`) y se seedea manualmente. El
  mapping `TAG_ALIASES` en `rb_sync.py` traduce tags sucios a genre slugs.

- **Now-playing en dos niveles**:
  - *On-demand*: cuando un usuario reproduce, un worker se conecta al
    stream con `Icy-MetaData: 1`, parsea el `StreamTitle`, publica en
    Redis pub/sub. API lo reenvía por WebSocket. Al cerrar último
    subscriber, el worker para.
  - *Ambient*: las 50 estaciones top (curadas + festivales activos) se
    pollean cada 60s con `IcecastMetadataStats` sin consumir stream.

- **Stream URL nunca se expone directo al navegador**. Frontend pide
  `/api/v1/stations/:slug/stream`, backend valida y redirige (302) al
  `stream_url` real. Permite logging, rate-limiting, y auditoría de
  streams rotos.

- **Sync idempotente**. `rb_sync.py` se puede ejecutar N veces seguidas
  sin duplicar ni romper datos. Upsert por `rb_uuid`. Tests verifican:
  dos runs seguidos → `count(stations)` estable.

---

## 8 · Variables de entorno (resumen)

Ver `.env.example` para lista completa y valores por defecto. Críticas:

- `DATABASE_URL`: postgres async, ej. `postgresql+asyncpg://user:pass@postgres:5432/radio`
- `REDIS_URL`: `redis://redis:6379/0`
- `JWT_SECRET`: para admin login, rotable
- `RB_USER_AGENT`: identificador para Radio-Browser, formato `radio.gofestivals/<version>`
- `ENV`: `dev` / `staging` / `prod`

---

## 9 · Gotchas conocidos

- **Radio-Browser SRV resolver**: el dominio `_api._tcp.radio-browser.info`
  devuelve varios servidores. Usar el primero que responda; si falla,
  probar el siguiente. No hardcodear un server concreto.

- **ICY metadata no siempre existe**. Algunas estaciones no mandan
  `Icy-MetaData`. El worker debe manejarlo silenciosamente, no loggear
  como error. `metaint == 0` → estación sin metadata, marcar flag y no
  reintentar en 24h.

- **HLS no soportado en fase 1**. Si `stream_url` termina en `.m3u8`,
  excluir del catálogo (marcar `status='unsupported'`). Considerar en
  fase 2 si hay demanda.

- **CORS y autoplay**. Reproductor HTML5 requiere interacción del usuario
  para iniciar. No intentar autoplay al cargar la página — es bloqueado
  por navegadores y es mal UX.

- **Postgres `geography` vs `geometry`**: si ves coordenadas en metros
  en lugar de grados, probablemente se mezclaron ambos tipos. El estándar
  del proyecto es **geography SRID 4326** (grados, esfera).

---

## 10 · Cómo pedir bien una tarea a Claude Code

Buenas tareas son **concretas, referenciadas y con criterio de éxito**:

**✓ Buena**:
> "Implementa el endpoint `GET /api/v1/stations` siguiendo la spec de la
> sección 07 del PDF. Parámetros: genre, country, curated, q, page, size
> (max 50). Caché Redis 60s. Test de integración: verificar paginación,
> filtros combinados, y que `size > 50` devuelve 422."

**✗ Mala**:
> "Hazme el endpoint de stations"

Razón: la mala no dice filtros, no menciona caché, no tiene criterio de
éxito. Resultado probable: código plausible pero que no encaja con el
resto del sistema.

Para tareas grandes, **romper en subtareas**. Para refactors, pedir que
primero explique el plan antes de tocar código.

---

## 11 · Deploy (staging / prod)

- **Host**: VPS Hetzner compartido con `formate.es`, `nyx`, …
- **Dominio staging**: `radio.gofestivals.eu`
- **Traefik**: ya corriendo en el VPS con Let's Encrypt. Red externa
  `traefik_proxy`. No tocar la config global del Traefik.
- **Repo en el VPS**: `/home/david/compose/radio-gofestivals`
- **Archivo de entorno**: `.env.production` (gitignored) con secretos
  rotados. Plantilla en `.env.production.example`.
- **Script principal**: `./infra/deploy/deploy.sh` — backup + build +
  migraciones + rolling up con healthchecks + smoke tests + rollback auto.
- **Logs**: `/var/log/radio/{rb_sync,health,backup}.log` (rotados 14 días)
- **Backups**: `/var/backups/radio-gofestivals/radio_<ts>.sql.gz` con
  retención 7 días (`backup-postgres.sh`).
- **Cron**: `infra/deploy/crontab.example` (sync diario 04:00 UTC,
  health-check cada 6h, backup 03:00 UTC).
- **Runbook completo**: `infra/deploy/README.md`.
- **No hacer `git push` desde el VPS**. El VPS es destino, no origen.

---

## 12 · Qué hacer cuando algo no encaja

Si durante una tarea Claude Code detecta que la spec contradice lo que
hay en el código, o que una decisión de este CLAUDE.md no tiene sentido
para el caso concreto:

1. **No silenciarlo**. Escribirlo explícitamente en la respuesta.
2. **Proponer alternativa**, no solo señalar el problema.
3. **Esperar confirmación** antes de desviarse de la spec.

Los documentos (este incluido) son guía, no dogma. Si hay una razón
genuina para desviarse, se discute y se actualiza el documento. Mejor
una conversación corta que código divergente.
