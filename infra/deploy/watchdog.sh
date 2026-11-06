#!/usr/bin/env bash
# watchdog.sh — recoge el estado de los contenedores de prod (el contenedor
# `scripts` no tiene socket de Docker) y lo pasa a `watchdog check`.
# Pensado para cron cada 15 min. Alertas en Telegram; ver ADR 006.
set -euo pipefail

cd "$(dirname "$0")/../.."

# Latido de classify-llm.sh (ADR 012): si el fichero existe y lleva demasiado sin tocarse, el job
# falla o dejó de ejecutarse. Aviso deduplicado por Redis (6 h); classify-llm.sh lo cierra al
# volver a funcionar. Best-effort: nunca debe tumbar el chequeo de contenedores.
HEARTBEAT="${CLASSIFY_LLM_HEARTBEAT:-/var/log/radio/classify-llm.last-ok}"
STALE_HOURS="${CLASSIFY_LLM_STALE_HOURS:-36}"
if [[ -f "$HEARTBEAT" ]]; then
  age_h=$(( ( $(date +%s) - $(stat -c %Y "$HEARTBEAT") ) / 3600 ))
  if (( age_h >= STALE_HOURS )); then
    docker compose --env-file .env.production -f docker-compose.prod.yml \
      run --rm -T --no-deps scripts watchdog notify --key classify-llm-stale \
      --message "classify-llm lleva ${age_h} h sin terminar bien (revisa /var/log/radio/classify.log y la sesión de Claude)" \
      || true
  fi
fi

CONTAINERS=(radio-api-prod radio-web-prod radio-icy-worker-prod radio-postgres-prod radio-redis-prod)

# Un contenedor inexistente simplemente no aparece: el watchdog lo reporta como "no encontrado".
docker inspect \
  -f '{{.Name}} {{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} {{.RestartCount}}' \
  "${CONTAINERS[@]}" 2>/dev/null \
  | docker compose --env-file .env.production -f docker-compose.prod.yml \
      run --rm -T scripts watchdog check --containers -
