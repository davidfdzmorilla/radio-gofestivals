# radio.gofestivals 🎛️

> Curated electronic-music online radio platform with 1300+ stations,
> personalized recommendations, hybrid user accounts and an admin panel.

🌐 **Live**: https://radio.gofestivals.eu
🇪🇸 **Español**: [README.md](./README.md)

---

## Features

### For listeners

- 🎵 **1300+ active stations** across a custom taxonomy of 20
  hierarchical genres (House, Techno, Trance, Drum & Bass, Ambient, …)
- 🎯 **Personalized recommendations** — a "For you" module on the home
  page and "Similar stations" on every station page, driven by genre
  affinity and co-listening ([design](./docs/recommendations-plan.md))
- 🔀 **Multi-stream with auto-fallback** — automatic recovery when a
  stream fails
- 📊 **Real-time spectrum analyzer** in the global player
- 🌍 **Bilingual UI** (English / Spanish) via next-intl
- 📱 **Mobile-first** responsive design

### User accounts (hybrid pattern)

- ❤️ **Save favorites anonymously** in localStorage — zero friction
- 👤 **Optional account** to sync favorites across devices
- 🔄 **Automatic migration** from localStorage to the backend on signup
- 👍 **Votes/likes system** that feeds the public ranking
- 📧 **Password reset by email** via Resend (no own SMTP)
- 🔒 **GDPR compliant**: soft delete, listening-history export and
  erasure, tracking only after consent

### Admin panel

- 📊 Dashboard with KPIs (active, curated, broken, average quality)
- 🛠️ Full station and genre CRUD with audit log
- 🚀 Async job system (Postgres-backed worker, executed by cron)
- 🔁 Stream operations (promote primary, bulk status changes)
- 🔍 Quality score + click trends + station similarity + health checks
  (nightly cron pipeline)

---

## Architecture

```
┌─ apps/web (Next.js 16, App Router, Turbopack)
│  ├─ Server Components (SSR/ISR) for public pages
│  ├─ Client Components for auth, favorites, player, "For you"
│  └─ next-intl 4 (en + es)
│
├─ apps/api (FastAPI + SQLAlchemy + Alembic)
│  ├─ Public REST API (/api/v1/stations, /genres, /recommended, …)
│  ├─ User auth (JWT, bcrypt, Redis rate limiting)
│  ├─ Admin auth (JWT with separate audience)
│  └─ Recommendations: on-the-fly blend over precomputed similarity
│
├─ packages/icy-worker (ICY metadata polling)
│  └─ Per-station "now playing" data (on-demand + ambient)
│
├─ packages/scripts (sync & maintenance CLI)
│  └─ rb_sync, quality scores, click trends, similarity, retention
│
├─ Postgres 16 + PostGIS (Docker)
├─ Redis 7 (cache + rate limit + pub/sub)
└─ Traefik (reverse proxy + TLS via Let's Encrypt)
```

---

## Stack

**Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic,
Pydantic v2, asyncpg, redis-py, bcrypt, httpx, structlog · managed
with `uv`

**Frontend**: TypeScript 6, Next.js 16 (App Router), React 19,
Tailwind CSS 4, Zod 4, Zustand 5, next-intl 4, lucide-react · tested
with Vitest 4 and Playwright · managed with `pnpm`

**Infrastructure**: Docker Compose (`python:3.12-slim` and
`node:22-alpine` images), Traefik (TLS via Let's Encrypt), Hetzner VPS,
Postgres 16 (postgis/postgis:16-3.4), Redis 7-alpine

**External services**: Resend (transactional email), Radio-Browser API
(station discovery)

---

## Repository layout

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
│   │   ├── alembic/versions/   # DB migrations
│   │   └── tests/              # Integration tests
│   │
│   └── web/                    # Next.js 16 frontend
│       ├── src/app/[locale]/   # Public pages (i18n)
│       ├── src/app/admin/      # Admin panel
│       ├── src/components/     # auth, layout, player, stations
│       ├── src/lib/            # api, users, admin, recs clients
│       └── messages/           # i18n keys (en, es)
│
├── packages/
│   ├── icy-worker/             # ICY metadata polling
│   └── scripts/                # rb_sync, quality, similarity, retention
│
├── docs/                       # Designs, roadmap and ADRs (docs/adr/)
├── infra/                      # Traefik, deploy, crontab
└── docker-compose.prod.yml     # Production stack
```

---

## Local development

Requires: Docker, Node 22+, pnpm, Python 3.12 and [uv](https://docs.astral.sh/uv/).

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
cd apps/api && uv run pytest          # backend (needs postgres+redis)
cd apps/web && pnpm test              # frontend (Vitest)
```

---

## Author

Built by [@davidfdzmorilla](https://github.com/davidfdzmorilla) —
full-stack developer based in Spain.

Part of the **gofestivals** ecosystem covering electronic-music
festivals and radio.

---

## License

[MIT](./LICENSE) © David Fernández Morilla

---

## Status

🟢 **Live** at https://radio.gofestivals.eu

Active development. Freshly shipped: **recommendation system MVP**
(nightly station-station similarity + personalized blend with
diversity and exploration — see
[docs/recommendations-plan.md](./docs/recommendations-plan.md) and ADR 004).

Roadmap (see `docs/`):

- Recommendations phase 2: listening duration (heartbeat), local GeoIP,
  artist signal from now-playing, CTR dashboard
- Email verification + welcome email
- Public user profiles (`/users/{username}`)
- Shared lists/collections
- Trending UI based on click_trends
- Privacy-first analytics integration
