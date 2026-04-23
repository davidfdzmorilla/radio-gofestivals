#!/usr/bin/env bash
# =============================================================================
# rollback.sh — restaura DB desde backup + baja imágenes anteriores
# Uso:
#   rollback.sh <backup_path|""> [prev_api_img] [prev_web_img]
# El backup path puede estar vacío si el deploy falló antes de poder crearlo.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT_DIR"

COMPOSE="docker compose --env-file .env.production -f docker-compose.prod.yml"
BACKUP="${1:-}"
PREV_API="${2:-}"
PREV_WEB="${3:-}"

LOG() { printf '[rollback] %s\n' "$*" >&2; }

LOG "starting rollback (backup='$BACKUP' prev_api='$PREV_API' prev_web='$PREV_WEB')"

# 1. DB restore
if [[ -n "$BACKUP" && -f "$BACKUP" ]]; then
  LOG "restoring postgres from $BACKUP"
  "$SCRIPT_DIR/restore-postgres.sh" "$BACKUP"
else
  LOG "no backup provided, skipping DB restore"
fi

# 2. Recover previous images (best-effort)
if [[ -n "$PREV_API" ]]; then
  LOG "retagging API image back to $PREV_API"
  docker tag "$PREV_API" radio-gofestivals/api:latest || true
fi
if [[ -n "$PREV_WEB" ]]; then
  LOG "retagging web image back to $PREV_WEB"
  docker tag "$PREV_WEB" radio-gofestivals/web:latest || true
fi

# 3. Bring services up with previous images
LOG "restarting services"
$COMPOSE up -d --wait --wait-timeout 120 || LOG "compose up returned non-zero"

# 4. Smoke
LOG "verifying /api/v1/_health"
if docker exec radio-api-prod curl -fsS http://127.0.0.1:8000/api/v1/_health >/dev/null 2>&1; then
  LOG "api responding after rollback"
else
  LOG "api NOT responding after rollback — manual intervention required"
fi

LOG "rollback finished; backup $BACKUP kept for re-rollback"
