#!/usr/bin/env bash
# watchdog.sh — recoge el estado de los contenedores de prod (el contenedor
# `scripts` no tiene socket de Docker) y lo pasa a `watchdog check`.
# Pensado para cron cada 15 min. Alertas en Telegram; ver ADR 006.
set -euo pipefail

cd "$(dirname "$0")/../.."

CONTAINERS=(radio-api-prod radio-web-prod radio-icy-worker-prod radio-postgres-prod radio-redis-prod)

# Un contenedor inexistente simplemente no aparece: el watchdog lo reporta como "no encontrado".
docker inspect \
  -f '{{.Name}} {{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} {{.RestartCount}}' \
  "${CONTAINERS[@]}" 2>/dev/null \
  | docker compose --env-file .env.production -f docker-compose.prod.yml \
      run --rm -T scripts watchdog check --containers -
