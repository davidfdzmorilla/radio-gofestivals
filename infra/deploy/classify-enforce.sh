#!/usr/bin/env bash
# =============================================================================
# classify-enforce.sh [args de classify-stations enforce] — aplica el veredicto del clasificador
# a la visibilidad (ADR 012, Fase 3a): oculta las rechazadas y repone las reclasificadas.
#
# Va detrás de classify-llm.sh en el cron (05:30 UTC) envuelto en run-job.sh. Si el cambio supera
# el tope (por defecto 5 % del catálogo visible) no aplica nada y sale con 4; el motivo queda en
# $RUN_JOB_DETAIL_FILE y llega en el aviso de Telegram. Para un despliegue inicial grande, a mano:
#     infra/deploy/classify-enforce.sh --max-change-pct 25
# Cualquier argumento se pasa tal cual a `classify-stations enforce` (--dry-run, --min-age-hours…).
# =============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE/../.." || exit 1
COMPOSE=(docker compose --env-file .env.production -f docker-compose.prod.yml)

detail() {
  echo "classify-enforce: $1" >&2
  [[ -n "${RUN_JOB_DETAIL_FILE:-}" ]] && printf '%s\n' "$1" > "$RUN_JOB_DETAIL_FILE"
  return 0
}

out="$(mktemp)"
err="$(mktemp)"
trap 'rm -f "$out" "$err"' EXIT

"${COMPOSE[@]}" run --rm -T scripts classify-stations enforce --notify "$@" > "$out" 2> "$err"
rc=$?
# El informe JSON es la última línea de stdout (los logs del proyecto también van a stdout).
report="$(grep '^{' "$out" | tail -n 1)"

case "$rc" in
  0)
    echo "{\"event\":\"classify_enforce_done\",\"report\":${report:-null}}"
    exit 0
    ;;
  4)
    detail "$(tail -c 300 "$err" | tr '\n' ' ')"
    exit 4
    ;;
  *)
    detail "fallo al aplicar la clasificación (código $rc): $(tail -c 300 "$err" | tr '\n' ' ')"
    exit "$rc"
    ;;
esac
