#!/usr/bin/env bash
# =============================================================================
# restore-postgres.sh <backup_file.sql.gz>
# =============================================================================
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <backup_file.sql.gz>" >&2
  exit 1
fi

FILE="$1"
if [[ ! -f "$FILE" ]]; then
  echo "backup file not found: $FILE" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT_DIR"

# shellcheck disable=SC1091
source .env.production

echo "[restore] restoring $FILE → database '${POSTGRES_DB}'" >&2

gunzip -c "$FILE" | docker compose --env-file .env.production -f docker-compose.prod.yml exec -T postgres \
  psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"

printf '{"event":"restore_done","file":"%s"}\n' "$FILE"
