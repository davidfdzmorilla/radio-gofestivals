#!/usr/bin/env bash
# run-job.sh <nombre> <comando...> — ejecuta un job de cron y alerta por Telegram si
# termina con código != 0. Conserva el código de salida del job.
#
#   0 3 * * * /home/david/compose/radio-gofestivals/infra/deploy/run-job.sh backup \
#       /home/david/compose/radio-gofestivals/infra/deploy/backup-postgres.sh >> /var/log/radio/backup.log 2>&1
set -uo pipefail

if [[ $# -lt 2 ]]; then
  echo "uso: run-job.sh <nombre> <comando...>" >&2
  exit 2
fi

JOB="$1"
shift

# El job puede dejar en $RUN_JOB_DETAIL_FILE una línea con la causa del fallo (p. ej. "límite de
# uso de la suscripción"); se añade al aviso para no recibir solo "falló con código N".
RUN_JOB_DETAIL_FILE="$(mktemp)"
export RUN_JOB_DETAIL_FILE
trap 'rm -f "$RUN_JOB_DETAIL_FILE"' EXIT

"$@"
rc=$?

if [[ $rc -ne 0 ]]; then
  cd "$(dirname "$0")/../.." || exit "$rc"
  detail="$(head -c 400 "$RUN_JOB_DETAIL_FILE" 2>/dev/null | tr '\n' ' ')"
  # --no-deps: no arrancar/esperar postgres, que puede ser justo lo que ha fallado.
  docker compose --env-file .env.production -f docker-compose.prod.yml \
    run --rm -T --no-deps scripts watchdog notify \
    --key "cron:${JOB}" \
    --message "Job '${JOB}' falló con código ${rc} en $(hostname) ($(date -u +%Y-%m-%dT%H:%MZ))${detail:+ — ${detail}}" \
    || echo "run-job: no se pudo enviar la alerta para '${JOB}'" >&2
fi

exit "$rc"
