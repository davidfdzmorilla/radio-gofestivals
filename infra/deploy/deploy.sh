#!/usr/bin/env bash
# =============================================================================
# radio.gofestivals · deploy.sh
# =============================================================================
# Deploy atómico del stack en el VPS. Backup previo, build, migraciones,
# rolling up con healthchecks y smoke tests. Rollback automático si algo falla.
#
# Variables:
#   FORCE=1       — permitir deploy con tree sucio
#   SKIP_DNS=1    — saltar verificación DNS (útil la primera vez)
#   SKIP_SMOKE=1  — saltar smoke tests (no recomendado)
#   DOMAIN=<...>  — override del dominio (default desde .env.production)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT_DIR"

COMPOSE="docker compose --env-file .env.production -f docker-compose.prod.yml"
START_TS=$(date -u +%s)
LOG() { printf '[deploy] %s\n' "$*" >&2; }
ERR() { printf '[deploy:ERR] %s\n' "$*" >&2; }

# ---------- 1. pre-flight --------------------------------------------------
LOG "pre-flight checks"

if [[ ! -f .env.production ]]; then
  ERR ".env.production not found"
  exit 1
fi
# shellcheck disable=SC1091
source .env.production
DOMAIN="${DOMAIN:-radio.gofestivals.eu}"

if ! command -v docker >/dev/null; then ERR "docker not installed"; exit 1; fi
if ! docker compose version >/dev/null 2>&1; then
  ERR "docker compose plugin not installed"; exit 1
fi

if ! docker network inspect traefik_proxy >/dev/null 2>&1; then
  ERR "external network 'traefik_proxy' does not exist"
  exit 1
fi

if [[ -z "${JWT_SECRET:-}" || ${#JWT_SECRET} -lt 32 ]]; then
  ERR "JWT_SECRET missing or shorter than 32 chars"; exit 1
fi
case "${JWT_SECRET,,}" in
  *change_me*|*dev_secret*|*placeholder*|*changeme*)
    ERR "JWT_SECRET looks like a placeholder; rotate it"; exit 1;;
esac

if [[ -z "${POSTGRES_PASSWORD:-}" || ${#POSTGRES_PASSWORD} -lt 12 ]]; then
  ERR "POSTGRES_PASSWORD missing or too short"; exit 1
fi
if [[ -z "${REDIS_PASSWORD:-}" || ${#REDIS_PASSWORD} -lt 12 ]]; then
  ERR "REDIS_PASSWORD missing or too short"; exit 1
fi

if [[ "${FORCE:-0}" != "1" ]]; then
  if [[ -n "$(git status --porcelain 2>/dev/null || true)" ]]; then
    ERR "git tree is dirty. Commit or pass FORCE=1"
    exit 1
  fi
fi

if [[ "${SKIP_DNS:-0}" != "1" ]]; then
  LOG "resolving $DOMAIN vs host IP"
  host_ip=$(hostname -I 2>/dev/null | awk '{print $1}' || true)
  dns_ip=$(getent hosts "$DOMAIN" 2>/dev/null | awk '{print $1}' | head -n1 || true)
  if [[ -n "$host_ip" && -n "$dns_ip" && "$host_ip" != "$dns_ip" ]]; then
    ERR "DNS mismatch: $DOMAIN -> $dns_ip but host IP is $host_ip. Override with SKIP_DNS=1"
    exit 1
  fi
fi

GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
export GIT_SHA DOMAIN
LOG "deploying sha=$GIT_SHA domain=$DOMAIN"

# ---------- 2. backup ------------------------------------------------------
LOG "backing up postgres before deploy"
BACKUP_PATH=""
if $COMPOSE ps postgres --status running 2>/dev/null | grep -q postgres; then
  BACKUP_PATH=$("$SCRIPT_DIR/backup-postgres.sh" | awk -F'"file":' '/backup_done/ {print $2}' | tr -d '", }' || true)
  LOG "backup path: ${BACKUP_PATH:-<none>}"
else
  LOG "postgres not running, skipping pre-deploy backup"
fi

# ---------- 3. build -------------------------------------------------------
LOG "building images (pull base layers)"
$COMPOSE build --pull

# Tag imágenes con el sha y latest
for svc in api web icy-worker scripts; do
  img="radio-gofestivals/${svc}:${GIT_SHA}"
  docker image tag "$img" "radio-gofestivals/${svc}:latest" 2>/dev/null || true
done

# ---------- 4. migrations --------------------------------------------------
LOG "running alembic migrations"
if ! $COMPOSE run --rm -T api alembic upgrade head; then
  ERR "migrations failed — NOT touching running services"
  exit 1
fi

# ---------- 5. rolling up --------------------------------------------------
LOG "rolling up services"
PREV_API_IMG=$(docker inspect --format='{{.Config.Image}}' radio-api-prod 2>/dev/null || echo "")
PREV_WEB_IMG=$(docker inspect --format='{{.Config.Image}}' radio-web-prod 2>/dev/null || echo "")

if ! $COMPOSE up -d --wait --wait-timeout 120; then
  ERR "compose up failed — invoking rollback"
  "$SCRIPT_DIR/rollback.sh" "${BACKUP_PATH:-}" "${PREV_API_IMG}" "${PREV_WEB_IMG}" || true
  exit 1
fi

# ---------- 6. smoke tests -------------------------------------------------
if [[ "${SKIP_SMOKE:-0}" != "1" ]]; then
  LOG "smoke tests against https://$DOMAIN"
  ok=1
  for path in "/" "/api/v1/genres" "/api/v1/_health"; do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://$DOMAIN$path" || echo "000")
    if [[ "$code" != "200" ]]; then
      ERR "smoke FAIL: GET $path -> $code"
      ok=0
    else
      LOG "smoke OK:   GET $path -> $code"
    fi
  done
  tls_info=$(curl -sI --max-time 10 "https://$DOMAIN/" | head -n1 || true)
  LOG "tls line: $tls_info"
  if [[ "$ok" != "1" ]]; then
    ERR "smoke tests failed — invoking rollback"
    "$SCRIPT_DIR/rollback.sh" "${BACKUP_PATH:-}" "${PREV_API_IMG}" "${PREV_WEB_IMG}" || true
    exit 1
  fi
fi

# ---------- 7. cleanup -----------------------------------------------------
LOG "pruning old images"
docker image prune -f --filter "label=org.opencontainers.image.source=https://github.com/gofestivals/radio" >/dev/null || true

# ---------- 8. final log ---------------------------------------------------
DURATION=$(( $(date -u +%s) - START_TS ))
cat <<EOF
{"event":"deploy_done","deploy_at":"$(date -u +%Y-%m-%dT%H:%M:%SZ)","git_sha":"$GIT_SHA","domain":"$DOMAIN","duration_seconds":$DURATION,"backup_path":"${BACKUP_PATH:-}"}
EOF
