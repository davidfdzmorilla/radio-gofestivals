# radio.gofestivals 🎛️

> Plataforma de radios online de música electrónica curada con 1300+
> emisoras, recomendaciones personalizadas, sistema híbrido de cuentas
> de usuario y panel de administración.

🌐 **En producción**: https://radio.gofestivals.eu
🇬🇧 **English**: [README.en.md](./README.en.md)

---

## Características

### Para oyentes

- 🎵 **1300+ emisoras activas** en una taxonomía propia de 20 géneros
  jerárquicos (House, Techno, Trance, Drum & Bass, Ambient, …)
- 🎯 **Recomendaciones personalizadas** — módulo «Para ti» en la home y
  «Emisoras similares» en cada ficha, por afinidad de géneros y
  co-escucha ([diseño](./docs/recommendations-plan.md))
- 🔀 **Multi-stream con auto-fallback** — recuperación automática si
  un stream falla
- 📊 **Analizador de espectro en tiempo real** en el reproductor global
- 🌍 **Interfaz bilingüe** (Inglés / Español) vía next-intl
- 📱 **Diseño mobile-first** responsive

### Cuentas de usuario (patrón híbrido)

- ❤️ **Guarda favoritos anónimamente** en localStorage — cero fricción
- 👤 **Cuenta opcional** para sincronizar favoritos entre dispositivos
- 🔄 **Migración automática** de localStorage al backend al registrarse
- 👍 **Sistema de votos/likes** que afecta el ranking público
- 📧 **Reset de contraseña por email** vía Resend (sin SMTP propio)
- 🔒 **Cumple GDPR**: soft delete, export y borrado del historial de
  escucha, tracking solo tras consentimiento

### Panel de administración

- 📊 Dashboard con KPIs (activas, curadas, rotas, calidad media)
- 🛠️ CRUD completo de emisoras y géneros con audit log
- 🚀 Sistema de jobs async (worker en Postgres, ejecutado por cron)
- 🔁 Operaciones de streams (promover primary, cambios masivos de status)
- 🔍 Score de calidad + tendencias de clicks + similitud entre emisoras
  + health checks (pipeline nocturno por cron)

---

## Arquitectura

```
┌─ apps/web (Next.js 16, App Router, Turbopack)
│  ├─ Server Components (SSR/ISR) para páginas públicas
│  ├─ Client Components para auth, favoritos, player, «Para ti»
│  └─ next-intl 4 (en + es)
│
├─ apps/api (FastAPI + SQLAlchemy + Alembic)
│  ├─ API REST pública (/api/v1/stations, /genres, /recommended, …)
│  ├─ Auth de usuarios (JWT, bcrypt, rate limiting en Redis)
│  ├─ Auth de admin (JWT con audience separado)
│  └─ Recomendaciones: blend on-the-fly sobre similitud precomputada
│
├─ packages/icy-worker (Polling de metadata ICY)
│  └─ Datos «ahora sonando» por emisora (on-demand + ambient)
│
├─ packages/scripts (CLI de sync y mantenimiento)
│  └─ rb_sync, quality scores, click trends, similitud, retención
│
├─ Postgres 16 + PostGIS (Docker)
├─ Redis 7 (cache + rate limit + pub/sub)
└─ Traefik (reverse proxy + TLS vía Let's Encrypt)
```

---

## Stack

**Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic,
Pydantic v2, asyncpg, redis-py, bcrypt, httpx, structlog · gestionado
con `uv`

**Frontend**: TypeScript 6, Next.js 16 (App Router), React 19,
Tailwind CSS 4, Zod 4, Zustand 5, next-intl 4, lucide-react · tests
con Vitest 4 y Playwright · gestionado con `pnpm`

**Infraestructura**: Docker Compose (imágenes `python:3.12-slim` y
`node:22-alpine`), Traefik (TLS vía Let's Encrypt), VPS Hetzner,
Postgres 16 (postgis/postgis:16-3.4), Redis 7-alpine

**Servicios externos**: Resend (email transaccional), Radio-Browser API
(descubrimiento de emisoras)

---

## Estructura del repositorio

```
.
├── apps/
│   ├── api/                    # Backend FastAPI
│   │   ├── app/
│   │   │   ├── api/v1/         # Endpoints REST (público + admin + users)
│   │   │   ├── models/         # ORM SQLAlchemy
│   │   │   ├── repos/          # Repository pattern
│   │   │   ├── services/       # Lógica de negocio
│   │   │   └── schemas/        # Schemas Pydantic
│   │   ├── alembic/versions/   # Migraciones de DB
│   │   └── tests/              # Tests de integración
│   │
│   └── web/                    # Frontend Next.js 16
│       ├── src/app/[locale]/   # Páginas públicas (i18n)
│       ├── src/app/admin/      # Panel de admin
│       ├── src/components/     # auth, layout, player, stations
│       ├── src/lib/            # Clientes api, users, admin, recs
│       └── messages/           # Claves i18n (en, es)
│
├── packages/
│   ├── icy-worker/             # Polling de metadata ICY
│   └── scripts/                # rb_sync, quality, similitud, retención
│
├── docs/                       # Diseños, roadmap y ADRs (docs/adr/)
├── infra/                      # Traefik, deploy, crontab
└── docker-compose.prod.yml     # Stack de producción
```

---

## Desarrollo local

Requiere: Docker, Node 22+, pnpm, Python 3.12 y [uv](https://docs.astral.sh/uv/).

### Backend

```bash
cp .env.example .env
docker compose up -d postgres redis

cd apps/api
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd apps/web
pnpm install
pnpm dev
```

### Tests

```bash
cd apps/api && uv run pytest          # backend (requiere postgres+redis)
cd apps/web && pnpm test              # frontend (Vitest)
```

---

## Autor

Construido por [@davidfdzmorilla](https://github.com/davidfdzmorilla) —
full-stack developer en España.

Parte del ecosistema **gofestivals** que cubre festivales y radio de
música electrónica.

---

## Licencia

[MIT](./LICENSE) © David Fernández Morilla

---

## Estado

🟢 **En producción** en https://radio.gofestivals.eu

Desarrollo activo. Recién desplegado: **MVP del sistema de
recomendación** (similitud emisora-emisora nocturna + blend
personalizado con diversidad y exploración — ver
[docs/recommendations-plan.md](./docs/recommendations-plan.md) y ADR 004).

Roadmap (ver `docs/`):

- Recomendaciones Fase 2: duración de escucha (heartbeat), GeoIP local,
  señal de artistas desde now-playing, dashboard de CTR
- Verificación de email + email de bienvenida
- Perfiles públicos de usuarios (`/users/{username}`)
- Listas/colecciones compartidas
- UI de Trending basada en click_trends
- Integración de analytics (privacy-first)
