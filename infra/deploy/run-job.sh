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

"$@"
rc=$?

if [[ $rc -ne 0 ]]; then
  cd "$(dirname "$0")/../.." || exit "$rc"
  # --no-deps: no arrancar/esperar postgres, que puede ser justo lo que ha fallado.
  docker compose --env-file .env.production -f docker-compose.prod.yml \
    run --rm -T --no-deps scripts watchdog notify \
    --key "cron:${JOB}" \
    --message "Job '${JOB}' falló con código ${rc} en $(hostname) ($(date -u +%Y-%m-%dT%H:%MZ))" \
    || echo "run-job: no se pudo enviar la alerta para '${JOB}'" >&2
fi

exit "$rc"
