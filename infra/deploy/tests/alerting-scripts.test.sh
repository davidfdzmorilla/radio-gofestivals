#!/usr/bin/env bash
# Pruebas de run-job.sh (causa del fallo en el aviso) y del chequeo de latido de watchdog.sh,
# con `docker` simulado: no envía alertas reales.
#   bash infra/deploy/tests/alerting-scripts.test.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_JOB="$HERE/../run-job.sh"
WATCHDOG="$HERE/../watchdog.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin"
FAILS=0

# docker simulado: anota cada `watchdog notify` (clave y mensaje); `inspect`/`check` no hacen nada.
cat > "$TMP/bin/docker" <<'STUB'
#!/usr/bin/env bash
if [[ " $* " == *" watchdog notify "* ]]; then
  key=""; msg=""
  while [[ $# -gt 0 ]]; do
    case "$1" in --key) key="$2"; shift ;; --message) msg="$2"; shift ;; esac
    shift
  done
  printf '%s|%s\n' "$key" "$msg" >> "$STUB_DIR/notify.log"
elif [[ " $* " == *" watchdog check "* ]]; then
  cat > /dev/null
fi
exit 0
STUB
chmod +x "$TMP/bin/docker"
export PATH="$TMP/bin:$PATH" STUB_DIR="$TMP"

ok() { if [[ "$2" == "$3" ]]; then echo "  ok   - $1"; else echo "  FAIL - $1"; echo "         esperado: $3"; echo "         obtenido: $2"; FAILS=$((FAILS + 1)); fi; }
reset() { rm -f "$TMP/notify.log" "$TMP/hb"; unset CLASSIFY_LLM_STALE_HOURS; }
notified() { cat "$TMP/notify.log" 2>/dev/null | tr '\n' ' ' | sed 's/ $//'; }

echo "run-job.sh"
reset
bash "$RUN_JOB" ok-job true; rc=$?
ok "job correcto: sale 0 y no avisa" "$rc|$(notified)" "0|"

reset
bash "$RUN_JOB" bad-job false; rc=$?
ok "job fallido sin causa: avisa con el código y sin guion de causa" "$rc|$(notified | grep -c 'bad-job. falló con código 1')|$(notified | grep -c ' — ')" "1|1|0"

reset
bash "$RUN_JOB" causa-job bash -c 'echo "límite de uso de la suscripción" > "$RUN_JOB_DETAIL_FILE"; exit 3'; rc=$?
ok "job fallido con causa: conserva el código y la causa va en el aviso" "$rc|$(notified | grep -c 'código 3.* — límite de uso de la suscripción')|$(notified | cut -d'|' -f1)" "3|1|cron:causa-job"

reset
bash "$RUN_JOB" largo-job bash -c 'printf "x%.0s" $(seq 1 2000) > "$RUN_JOB_DETAIL_FILE"; exit 1'
ok "la causa se acota (400 caracteres)" "$([[ $(notified | wc -c) -lt 700 ]] && echo si || echo no)" "si"

reset
bash "$RUN_JOB" ok-con-causa bash -c 'echo "causa vieja" > "$RUN_JOB_DETAIL_FILE"; exit 0'
ok "un job que sale 0 no avisa aunque deje texto en el fichero de causa" "$(notified)" ""

echo "watchdog.sh · latido de classify-llm"
reset
CLASSIFY_LLM_HEARTBEAT="$TMP/hb" bash "$WATCHDOG"; rc=$?
ok "sin fichero de latido (nunca se ha ejecutado): no avisa y no rompe el chequeo" "$(notified)|$rc" "|0"

reset; touch "$TMP/hb"
CLASSIFY_LLM_HEARTBEAT="$TMP/hb" bash "$WATCHDOG"; rc=$?
ok "latido reciente: no avisa" "$(notified)|$rc" "|0"

reset; touch -d "40 hours ago" "$TMP/hb"
CLASSIFY_LLM_HEARTBEAT="$TMP/hb" bash "$WATCHDOG"
ok "latido de 40 h: avisa con la clave de obsolescencia y las horas" "$(notified | cut -d'|' -f1) $(notified | grep -c 'lleva 40 h')" "classify-llm-stale 1"

reset; touch -d "20 hours ago" "$TMP/hb"
CLASSIFY_LLM_HEARTBEAT="$TMP/hb" CLASSIFY_LLM_STALE_HOURS=12 bash "$WATCHDOG"
ok "el umbral es configurable (20 h > 12 h)" "$(notified | cut -d'|' -f1)" "classify-llm-stale"

reset; touch -d "35 hours ago" "$TMP/hb"
CLASSIFY_LLM_HEARTBEAT="$TMP/hb" bash "$WATCHDOG"
ok "justo por debajo del umbral por defecto (35 h < 36 h): no avisa" "$(notified)" ""

echo
if [[ "$FAILS" -eq 0 ]]; then echo "OK"; else echo "$FAILS fallo(s)"; exit 1; fi
