#!/usr/bin/env bash
# =============================================================================
# backup-postgres.sh — dump de la DB productiva con rotación 7 días
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT_DIR"

BACKUP_DIR="${BACKUP_DIR:-/var/backups/radio-gofestivals}"
mkdir -p "$BACKUP_DIR"

TS=$(date -u +%Y%m%dT%H%M%SZ)
FILE="$BACKUP_DIR/radio_${TS}.sql.gz"

# shellcheck disable=SC1091
source .env.production

docker compose --env-file .env.production -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
    --no-owner --clean --if-exists \
  | gzip -9 > "$FILE"

SIZE=$(du -h "$FILE" | cut -f1)

# Retention: 7 días
find "$BACKUP_DIR" -name "radio_*.sql.gz" -mtime +7 -delete 2>/dev/null || true

printf '{"event":"backup_done","file":"%s","size":"%s","ts":"%s"}\n' "$FILE" "$SIZE" "$TS"
