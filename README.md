# radio.gofestivals 🎛️

> Plataforma de radios online de música electrónica curada con 1300+ 
> emisoras, sistema híbrido de cuentas de usuario y panel de administración.

🌐 **En producción**: https://radio.gofestivals.eu  
🇬🇧 **English**: [README.en.md](./README.en.md)

---

## Características

### Para oyentes

- 🎵 **1300+ emisoras activas** en 12 géneros (House, Techno, Trance, 
  Drum & Bass, Ambient, Dubstep, Hardstyle, Breakbeat, Electronic, 
  Chill Out, Dance, EDM)
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
- 🔒 **Cumple GDPR** con soft delete y rotación de email

### Panel de administración

- 📊 Dashboard con KPIs (activas, curadas, rotas, calidad media)
- 🛠️ CRUD completo de emisoras y géneros con audit log
- 🚀 Sistema de jobs async (worker en Postgres, ejecutado por cron)
- 🔁 Operaciones de streams (promover primary, cambios masivos de status)
- 🔍 Score de calidad + tendencias de clicks + health checks (cron nocturno)

---

## Arquitectura

```
┌─ apps/web (Next.js 14, App Router)
│  ├─ Server Components (SSR) para páginas públicas
│  ├─ Client Components para auth, favoritos, player
│  └─ next-intl (en + es)
│
├─ apps/api (FastAPI + SQLAlchemy + Alembic)
│  ├─ API REST pública (/api/v1/stations, /genres, etc)
│  ├─ Auth de usuarios (JWT, bcrypt, rate limiting)
│  ├─ Auth de admin (JWT con audience separado)
│  └─ Worker async de jobs (ejecutado por cron)
│
├─ apps/icy-worker (Polling de metadata ICY)
│  └─ Datos "ahora sonando" por emisora
│
├─ Postgres 16 + PostGIS (Docker)
├─ Redis 7 (cache + rate limit)
└─ Traefik (reverse proxy + TLS vía Let's Encrypt)
```

---

## Stack

**Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, 
Pydantic v2, asyncpg, bcrypt, passlib, slowapi (rate limit), httpx

**Frontend**: TypeScript, Next.js 14 (App Router), React 18, Tailwind CSS, 
Zod, lucide-react, next-intl

**Infraestructura**: Docker Compose, Traefik (TLS vía Let's Encrypt), 
VPS Hetzner, Postgres 16 (postgis/postgis:16-3.4), Redis 7-alpine

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
│   ├── web/                    # Frontend Next.js 14
│   │   ├── src/app/[locale]/   # Páginas públicas (i18n)
│   │   ├── src/app/admin/      # Panel de admin
│   │   ├── src/components/     # auth, layout, player, stations
│   │   ├── src/lib/            # Clientes api, users, admin
│   │   └── messages/           # Claves i18n (en, es)
│   │
│   └── icy-worker/             # Polling de metadata ICY
│
├── docs/                       # Documentación de arquitectura y roadmap
├── infra/                      # Docker, scripts de deploy
└── docker-compose.prod.yml     # Stack de producción
```

---

## Desarrollo local

Requiere: Docker, Node 20+, Python 3.12, pnpm.

### Backend

```bash
cd apps/api
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend

```bash
cd apps/web
pnpm install
pnpm dev
```

### Todos los servicios (Docker)

```bash
docker compose up
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

Desarrollo activo. Roadmap (ver `docs/`):

- Verificación de email + email de bienvenida
- Perfiles públicos de usuarios (`/users/{username}`)
- Listas/colecciones compartidas
- Comentarios y sistema de follows
- UI de Trending basada en click_trends
- Integración de analytics (privacy-first)