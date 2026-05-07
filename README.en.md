# radio.gofestivals 🎛️

> Curated electronic music radio platform with 1300+ stations, hybrid 
> user accounts, and a powerful admin panel.

🌐 **Live**: https://radio.gofestivals.eu  
🇪🇸 **Spanish**: [README.es.md](./README.es.md)

---

## Features

### For listeners

- 🎵 **1300+ active stations** across 12 genres (House, Techno, Trance, 
  Drum & Bass, Ambient, Dubstep, Hardstyle, Breakbeat, Electronic, 
  Chill Out, Dance, EDM)
- 🔀 **Multi-stream auto-fallback** — graceful recovery when a stream breaks
- 📊 **Real-time spectrum analyzer** in the global player
- 🌍 **Bilingual interface** (English / Spanish) via next-intl
- 📱 **Mobile-first responsive** design

### User accounts (hybrid pattern)

- ❤️ **Save favorites anonymously** in localStorage — zero friction
- 👤 **Optional account** to sync favorites across devices
- 🔄 **Automatic migration** from localStorage to backend on signup
- 👍 **Vote/like system** affecting public ranking
- 📧 **Email password reset** via Resend (no SMTP setup needed)
- 🔒 **GDPR-compliant** soft delete with email rotation

### Admin panel

- 📊 Dashboard with KPIs (active, curated, broken, avg quality)
- 🛠️ Full CRUD for stations and genres with audit log
- 🚀 Async job system (Postgres-backed worker, cron-driven)
- 🔁 Stream operations (promote primary, bulk status changes)
- 🔍 Quality scoring + click trends + health checks (nightly cron)

---

## Architecture

```
┌─ apps/web (Next.js 14, App Router)
│  ├─ Server Components (SSR) for public pages
│  ├─ Client Components for auth, favorites, player
│  └─ next-intl (en + es)
│
├─ apps/api (FastAPI + SQLAlchemy + Alembic)
│  ├─ Public REST API (/api/v1/stations, /genres, etc)
│  ├─ User auth (JWT, bcrypt, rate limiting)
│  ├─ Admin auth (separate JWT audience)
│  └─ Async job worker (run via cron)
│
├─ apps/icy-worker (ICY metadata polling)
│  └─ "Now playing" data per station
│
├─ Postgres 16 + PostGIS (Docker)
├─ Redis 7 (cache + rate limit)
└─ Traefik (reverse proxy + TLS via Let's Encrypt)
```

---

## Stack

**Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, 
Pydantic v2, asyncpg, bcrypt, passlib, slowapi (rate limit), httpx

**Frontend**: TypeScript, Next.js 14 (App Router), React 18, Tailwind CSS, 
Zod, lucide-react, next-intl

**Infrastructure**: Docker Compose, Traefik (TLS via Let's Encrypt), 
Hetzner VPS, Postgres 16 (postgis/postgis:16-3.4), Redis 7-alpine

**External services**: Resend (transactional email), Radio-Browser API 
(station discovery)

---

## Repository structure

```
.
├── apps/
│   ├── api/                    # FastAPI backend
│   │   ├── app/
│   │   │   ├── api/v1/         # REST endpoints (public + admin + users)
│   │   │   ├── models/         # SQLAlchemy ORM
│   │   │   ├── repos/          # Repository pattern
│   │   │   ├── services/       # Business logic
│   │   │   └── schemas/        # Pydantic schemas
│   │   ├── alembic/versions/   # Database migrations
│   │   └── tests/              # Integration tests
│   │
│   ├── web/                    # Next.js 14 frontend
│   │   ├── src/app/[locale]/   # Public pages (i18n)
│   │   ├── src/app/admin/      # Admin panel
│   │   ├── src/components/     # auth, layout, player, stations
│   │   ├── src/lib/            # api, users, admin clients
│   │   └── messages/           # i18n keys (en, es)
│   │
│   └── icy-worker/             # ICY metadata polling
│
├── docs/                       # Architecture docs and roadmap
├── infra/                      # Docker, deploy scripts
└── docker-compose.prod.yml     # Production stack
```

---

## Local development

Requires: Docker, Node 20+, Python 3.12, pnpm.

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

### All services (Docker)

```bash
docker compose up
```

---

## Author

Built by [@davidfdzmorilla](https://github.com/davidfdzmorilla) — 
full-stack developer based in Spain.

Part of the **gofestivals** ecosystem covering electronic music 
festivals and radio.

---

## License

[MIT](./LICENSE) © David Fernández Morilla

---

## Status

🟢 **Live in production** at https://radio.gofestivals.eu

Active development. Roadmap (see `docs/`):

- Email verification + welcome email
- Public user profiles (`/users/{username}`)
- Shared playlists / collections
- Comments and following
- Trending UI based on click_trends
- Analytics integration (privacy-first)
