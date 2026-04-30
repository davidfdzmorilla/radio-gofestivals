# Users MVP Plan · radio.gofestivals

Plan documentado el 30 abril 2026 tras admin plan completo.

## Visión

Producto público con concepto de "usuario" para guardar favoritos y dar
likes (votes) sin perder cero fricción para usuarios casuales.

Patrón híbrido: anónimo por defecto (localStorage), opcional crear
cuenta para sync entre dispositivos.

## Decisiones técnicas

| # | Decisión | Elegido |
|---|---|---|
| 1 | Password hashing | bcrypt (igual que admin) |
| 2 | Auth | JWT en localStorage, expiración 30 días |
| 3 | Rate limit | Estricto: register 3/h IP, login 5/min IP, vote 10/min user |
| 4 | Email reset | SÍ en MVP usando Resend (decisión informada) |
| 5 | Email verification | NO en MVP (apuntable, requiere SMTP setup ya hecho) |
| 6 | GDPR | Soft delete + DELETE /auth/me con reauth password |
| 7 | Password reset tokens | UUID + expires_at 1 hora + used_at |

## Schema DB · migración 0012

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  
  -- Futuro-proof (nullable, NO usados en MVP)
  username TEXT,
  display_name TEXT,
  bio TEXT,
  avatar_url TEXT,
  is_public BOOLEAN DEFAULT false,
  email_verified_at TIMESTAMPTZ,
  
  -- GDPR
  deleted_at TIMESTAMPTZ,
  
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE UNIQUE INDEX uq_users_email 
  ON users (email) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX uq_users_username 
  ON users (username) WHERE deleted_at IS NULL AND username IS NOT NULL;
CREATE INDEX idx_users_created_at ON users (created_at DESC);


CREATE TABLE user_favorites (
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  station_id UUID NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
  PRIMARY KEY (user_id, station_id)
);
CREATE INDEX idx_user_favorites_user 
  ON user_favorites (user_id, created_at DESC);


CREATE TABLE user_votes (
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  station_id UUID NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
  PRIMARY KEY (user_id, station_id)
);


CREATE TABLE password_reset_tokens (
  token UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE INDEX idx_reset_tokens_user 
  ON password_reset_tokens (user_id, created_at DESC);


ALTER TABLE stations 
  ADD COLUMN votes_local INTEGER NOT NULL DEFAULT 0;
CREATE INDEX idx_stations_votes_local 
  ON stations (votes_local DESC) WHERE status = 'active';

## Endpoints (12 + 2 modificados)

Auth (4):
- POST /api/v1/auth/register
- POST /api/v1/auth/login
- GET  /api/v1/auth/me
- DELETE /api/v1/auth/me (requires reauth password)

Password reset (2):
- POST /api/v1/auth/forgot-password (anti-enum)
- POST /api/v1/auth/reset-password

Favorites (4):
- GET  /api/v1/favorites
- POST /api/v1/favorites/{station_id}
- DELETE /api/v1/favorites/{station_id}
- POST /api/v1/favorites/migrate (anonymous → registered)

Votes (2):
- POST /api/v1/stations/{id}/like
- DELETE /api/v1/stations/{id}/like

Modificados (existentes):
- GET /api/v1/stations/{id} → añadir is_favorite + user_voted si JWT
- GET /api/v1/stations → añadir is_favorite + user_voted si JWT

## UX flows

Flow 1 · Anónimo guarda fav:
  Click ❤ → localStorage + toast "Saved. Sign up to sync"

Flow 2 · Sign up (con favs locales):
  Submit form → 201 + token → POST /favorites/migrate → banner verde

Flow 3 · Login en nuevo device:
  Login → token → GET /favorites → render ❤ rojo

Flow 4 · Forgot password:
  /forgot-password → email enviado → /reset-password?token=xxx
  → POST /auth/reset-password → redirect /login

Flow 5 · Like (vote):
  Anónimo → modal o redirect a /login (return_url)
  Auth → POST /stations/{id}/like → ❤ rojo + counter +1

Flow 6 · Delete account:
  /profile → click delete → modal "type password" → POST /auth/delete-account
  → soft delete + email rotated + redirect home

## Setup Resend (operacional)

Antes de programar:
1. Crear cuenta en https://resend.com (gratis)
2. Verificar dominio gofestivals.eu (3 DNS records: SPF, DKIM, DMARC)
3. Email "from": noreply@gofestivals.eu
4. API key en .env.production: RESEND_API_KEY=re_xxxxxxxxxxxx

Free tier: 3000 emails/mes + 100/día

## Soporte

- Repo público: github.com/davidfdzmorilla/radio-gofestivals
- Página /support con instrucción "Crea issue en GitHub"
- Setup labels: support, bug, feature
- Sin reply-to monitor en emails (noreply)

## Roadmap

Sesión 1 · Backend (~4-5h):
- Migración 0012
- Models + repos (users, user_favorites, user_votes, password_reset_tokens)
- Schemas Pydantic (UserOut, AuthResponse, FavoriteOut, VoteResponse...)
- Service layer (auth, favorites, votes, email_resend)
- 12 endpoints + modificación de /stations* para incluir is_favorite/user_voted
- Email templates (HTML + plaintext) para reset password
- Rate limiting con slowapi/Redis
- Tests integración

Sesión 2 · Frontend (~4-5h):
- Lib: auth, favorites (LocalStorage + Backend providers), votes
- Hook useAuth con context
- Componentes:
  - HeartButton (con isAnonymous logic)
  - LikeButton (requires auth)
  - AuthModal (login + signup)
  - ForgotPasswordModal
  - UserMenu (header)
- Páginas:
  - /signup, /login, /forgot-password
  - /reset-password?token=xxx
  - /favorites
  - /profile (settings + delete account)
  - /support (GitHub issues link)
- Migración localStorage → backend al registrar
- Integración HeartButton/LikeButton en station cards

Sesión 3 (futuro, NO en MVP):
- Email verification
- Avatar upload (a Cloudflare R2 o S3)
- Perfiles públicos /users/{username}

Total MVP estimado: ~8-10h en 2 sesiones.

## NO incluido en MVP (apuntable)

- Email verification (requiere flujo extra)
- Perfiles públicos /users/{username}
- Listas/colecciones compartidas
- Comments en stations
- Following entre users
- Recommendations basadas en favs
- Social sign-in (Google, Apple)
- Avatar upload
- Email export GDPR Article 20
- TTL cleanup users deleted_at > 30 días

