# Admin Frontend · Plan de Implementación

**Fecha de planning**: 2026-04-28  
**Versión**: 1.0 (post-investigación del backend existente)

---

## Estado actual

### Backend: ya construido y funcional
apps/api/app/api/v1/admin/
├── auth.py        → login + me (JWT, rate limited 5/60s)
├── stations.py    → list_pending + curate (approve/reject/reclassify)
└── genres.py      → CRUD completo de géneros
apps/api/app/services/admin/
├── auth.py        → bcrypt, JWT con jose, last_login persistido
├── stations.py    → curation flow + auto_curate command
└── genres.py      → CRUD con cache invalidation
apps/api/app/models/admin.py
├── Admin          → email, password_hash, name, active, last_login_at
└── CurationLog    → audit trail (admin_id, station_id, decision, notes)

**Verificado funcionando** (2026-04-28):
- `POST /admin/auth/login` → JWT válido (24h expiry)
- `GET /admin/auth/me` → user info correcta + last_login persiste
- `GET /admin/stations/pending` → responde 200 (vacío en condiciones normales)

**Admin user existente**: davidfdzmorilla@gmail.com (UUID: 1542874c-...)

### Frontend: cero UI admin

No existe ruta `/admin/*` ni componentes admin en `apps/web/src/`.

---

## Diagnóstico del flow operacional real
04:00 UTC  rb_sync          → INSERT stations nuevas con default 'pending' (DB)
06:00 UTC  health-check     → promueve 'pending' → 'active' si streams vivos
12/18/00   health-check     → continúa promoviendo

**Implicaciones**:

1. **`status='pending'` solo existe ~2-6h** entre INSERT de rb_sync y siguiente health-check
2. El endpoint `/admin/stations/pending` siempre devuelve queue casi vacía
3. **El flow de "approve/reject pending"** no se puede usar en práctica
4. **El campo `curated`** es el verdadero diferenciador (140 curated = destacadas en home)
5. Las 140 stations curated probablemente se marcaron via comando `auto_curate` ejecutado por agente en sesión anterior, sin UI

---

## Funcionalidades del admin (priorizadas)

### Tier 1 · CRUD básico de stations (MVP)
**Objetivo**: poder gestionar curated/active/inactive desde UI sin SQL directo

- Login + sesión persistente
- Lista paginada de TODAS las stations con filtros (no solo pending)
- Toggle `curated` (true/false)
- Marcar `status` (active/inactive manual override)
- Edit géneros M:N de una station

### Tier 2 · Gestión de géneros
- Lista jerárquica de géneros (con parent_id)
- CRUD individual (POST/PUT/DELETE ya existen en backend)
- Color picker, sort_order, descripción

### Tier 3 · Operaciones
- Force sync now (trigger manual de rb_sync)
- Reasignar primary stream de una station multi-stream
- Ejecutar auto_curate con threshold configurable
- Marcar station inactive/active manualmente

### Tier 4 · Observabilidad
- Dashboard con counts por status
- Últimos sync runs (logs accesibles)
- Top stations por click_trend (cuando esté maduro)
- Curation log viewer (quién hizo qué cuándo)

---

## Decisiones arquitectónicas

### Auth method
**Decisión**: JWT propio (ya implementado backend con `jose`)

- Backend ya hace login + emite JWT 24h
- Frontend almacena en `localStorage` (preferred) o cookie httpOnly
- Header `Authorization: Bearer <token>` en cada request admin
- Logout = remove token del cliente (no hay revocación server-side)

### Hosting del admin
**Decisión**: misma app Next.js, ruta `/admin/*` protegida

Razones:
- Cero infraestructura nueva (Traefik, container, DNS)
- Middleware Next.js protege rutas `/admin` con check de JWT
- Despliegue unificado con el web actual
- Para 1 admin (tú), separar es overkill

### UI framework
**Decisión**: continuar con shadcn/ui (ya en uso)

- Coherencia visual con resto del producto
- Tabla compleja con filtros/paginación: shadcn `<Table>` + `<Pagination>` + lucide icons
- Forms: shadcn `<Form>` + react-hook-form + zod (probablemente ya en stack)

### Roles
**Decisión**: solo "admin" por ahora, preparar para futuro

- Tabla `admins` actual no tiene `role` column
- Si en futuro se necesita "editor" vs "super-admin", añadir migración
- KISS para hoy

### Auditoría
**Decisión**: extender `curation_log` existente

- Tabla ya capta admin_id + station_id + decision + notes
- Para tier 1, añadir `action` ENUM: 'toggle_curated', 'edit_genres', 'change_status'
- Migración menor para nuevo enum

---

## Backend gaps necesarios

### Tier 1
GET    /admin/stations                    → list paginated con filtros
(no solo pending)
PATCH  /admin/stations/{id}               → toggle curated, change status,
update genre_ids
GET    /admin/stations/{id}               → detail completo (incluyendo
streams + audit history)

### Tier 2 (mínimos cambios)
- GET /admin/genres (list ordered) — puede que falte
- Verificar que CRUD endpoints actuales (POST/PUT/DELETE) son suficientes

### Tier 3
POST   /admin/operations/force-sync       → trigger rb_sync command
POST   /admin/operations/auto-curate      → ejecutar auto_curate con params
PATCH  /admin/streams/{id}                → marcar primary, change status

### Tier 4
GET    /admin/stats/overview              → counts agregados
GET    /admin/curation-log                → paginated log con filtros
GET    /admin/health-checks               → últimos N checks con stats

---

## Roadmap de sesiones

### Sesión 1 · Backend gaps Tier 1 (~1.5-2h)
- Migración: añadir 'edit_metadata' al enum curation_decision (o crear tabla audit_log nueva)
- Endpoint GET /admin/stations con filtros (status, curated, country, search)
- Endpoint PATCH /admin/stations/{id} con scope completo
- Endpoint GET /admin/stations/{id} (detail con streams + audit)
- Tests de integración

### Sesión 2 · Frontend setup + auth (~2h)
- Estructura `/admin/*` en Next.js app router
- Middleware de auth check
- Login page (formulario simple)
- localStorage del JWT
- Layout `/admin` con header (logo, user info, logout)
- Logout flow + redirect a login si JWT expirado

### Sesión 3 · Lista de stations (~2-3h)
- Página `/admin/stations` con tabla
- Filtros: status (multi-select), curated (yes/no/all), country, search por nombre/slug
- Paginación con cursor o offset
- Acciones rápidas: toggle curated (badge clickable), abrir edit
- Indicadores visuales: count de streams, score, last sync

### Sesión 4 · Edit individual + géneros (~2-3h)
- Página/modal `/admin/stations/{id}/edit`
- Form: name, slug, status, curated, géneros (multi-select)
- Save → PATCH backend + audit log automático
- Vista de streams (tabla read-only por ahora)
- Vista de audit history (últimas N decisiones sobre esta station)

### Sesión 5 · Géneros (~1.5h)
- Página `/admin/genres`
- Lista jerárquica con drag&drop de sort_order (opcional)
- Modal de create/edit con color picker
- Delete con confirmación si hay stations asociadas

### Sesión 6+ · Tier 3 y 4 (TBD)
- Operations panel
- Dashboard con stats
- Curation log viewer

**Total Tier 1+2 funcional**: 5 sesiones, ~10-13h

---

## Pendientes / decisiones para próxima sesión

- [ ] Confirmar password manager para password del admin (1Password, etc.) o
      crear flow de cambio de password
- [ ] Decidir si invalidamos JWT en backend (logout server-side) o solo client
- [ ] Decidir si necesitamos password reset flow ya, o lo posponemos
- [ ] Revisar si hay restricción CSRF necesaria en endpoints admin
- [ ] Test del rate limit de login en producción (5 intentos / 60s)
- [ ] Decidir si añadimos 2FA para admin (futuro, no urgente)

---

## Notas operacionales

- Backend admin **ya funciona** end-to-end. Verificado con curl 2026-04-28.
- Frontend desde cero pero consume API existente.
- El comando `auto_curate` debe seguir funcionando como helper SQL para casos
  bulk (ej. promover 50 stations a curated en una iteración).
- Mantener `curation_log` como audit canónico independiente de UI.

---

## Tier 3 · Plan detallado · 29 abril 2026

### Decisión arquitectónica · sistema async

**Elegido**: Job table en Postgres + worker en container `scripts` (opción D
del análisis).

**Alternativas descartadas**:
- BackgroundTasks de FastAPI: rompe el patrón "container efímero", acopla
  comandos largos al API container
- ARQ con worker dedicado: production-grade pero overkill para uso real
  (1-2 ops/mes)
- subprocess + docker socket desde API: riesgo de seguridad inaceptable

**Por qué la opción elegida**:
- Coherente con el patrón existente (crons del host ejecutan
  docker compose run --rm scripts CMD)
- Cero infraestructura nueva (reusa container scripts)
- Auditable vía SELECT * FROM admin_jobs en Postgres
- Latencia ~1 min aceptable para uso esporádico

### Schema · admin_jobs

CREATE TABLE admin_jobs (
  id BIGSERIAL PRIMARY KEY,
  command TEXT NOT NULL,
  params_json JSONB,
  status TEXT NOT NULL,
  result_json JSONB,
  stderr_tail TEXT,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  admin_id UUID REFERENCES admins(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

Status enum: pending | running | success | failed | timeout

Worker pickea con FOR UPDATE SKIP LOCKED (configuración: 1 job a la vez
globalmente, no concurrencia paralela).

### Comandos expuestos (6)

Todos los comandos safe del CLI Typer existente:

- Run sync               -> rb_sync run                  (defaults)
- Run health-check       -> rb_sync health-check         (defaults)
- Auto-curate            -> rb_sync auto-curate-top      (params)
- Recompute quality      -> compute-quality-scores       (defaults)
- Snapshot clickcounts   -> snapshot-clickcounts         (defaults)
- Recompute click trends -> compute-click-trends         (defaults)

Stream operations (promote primary, bulk inactive) se posponen a
Sesión 6.3 (paradigma distinto: PATCH endpoints simples, no CLI exec).

### Decisiones UX

1. Params: defaults para 5 comandos (1 click), modal con form solo
   para auto-curate (min_quality, limit, country, dry_run)
2. Concurrencia: 1 job a la vez globalmente (FOR UPDATE SKIP LOCKED)
3. Output captura: result_json (event final estructurado) +
   stderr_tail (50 líneas si error)
4. Worker: cron del host cada minuto (* * * * *)
5. Polling frontend: 5s mientras job en estado running

### Roadmap

Sesión 6.1 · Backend + Worker (~2-3h):
- Migración alembic: tabla admin_jobs
- Schemas Pydantic
- Repo admin_jobs (insert, list, get_by_id, claim_next, complete)
- Endpoint POST /admin/operations/run (encola)
- Endpoint GET /admin/operations/jobs (paginado, filtros)
- Endpoint GET /admin/operations/jobs/{id} (detalle)
- Comando CLI nuevo: run-pending-admin-jobs (en packages/scripts)
- Tests de integración
- Cron line en crontab.example (operador instala manual)

Sesión 6.2 · Frontend (~2-3h):
- Página /admin/operations
- 6 botones (5 directos + 1 con modal de params)
- Tabla de jobs históricos con paginación
- Detalle de job (modal o página) con result_json + stderr_tail
- Polling automático mientras hay job running
- Nav actualizado con "Operations"

Sesión 6.3 · Stream operations (futuro, separada):
- PATCH /admin/streams/{id}/promote-primary
- Bulk endpoints (mark inactive, etc)
- UI en /admin/stations/[id] (detail) con acciones por stream

Total Tier 3 estimado: 5-6 horas (2-3 sesiones).

### Pendientes operacionales tras Tier 3

- Documentar en CLAUDE.md el patrón admin_jobs para próximos agentes
- Decidir TTL de jobs viejos (cleanup mensual?)
- Considerar timeout configurable por comando

