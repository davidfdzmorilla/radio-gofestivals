#!/usr/bin/env bash
# Pruebas de classify-enforce.sh con `docker` simulado.
#   bash infra/deploy/tests/classify-enforce.test.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/../classify-enforce.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin"
FAILS=0

cat > "$TMP/bin/docker" <<'STUB'
#!/usr/bin/env bash
echo "$*" > "$STUB_DIR/docker.args"
case "${STUB_MODE:-ok}" in
  ok)  echo 'log: algo'; echo '{"hidden": 3, "unhidden": 1, "visible_before": 100, "visible_after": 98}'; exit 0 ;;
  cap) echo "cambio masivo bloqueado: se ocultarían 90 emisoras (18.0 % de 500 visibles) > tope 5 %" >&2; exit 4 ;;
  boom) echo "Traceback: kaboom" >&2; exit 2 ;;
esac
STUB
chmod +x "$TMP/bin/docker"
export PATH="$TMP/bin:$PATH" STUB_DIR="$TMP"

ok() { if [[ "$2" == "$3" ]]; then echo "  ok   - $1"; else echo "  FAIL - $1"; echo "         esperado: $3"; echo "         obtenido: $2"; FAILS=$((FAILS + 1)); fi; }
run() { RUN_JOB_DETAIL_FILE="$TMP/detail" bash "$SCRIPT" "$@" > "$TMP/out" 2> "$TMP/err"; echo $?; }

echo "classify-enforce.sh"
: > "$TMP/detail"; export STUB_MODE=ok
ok "éxito: sale 0 y no deja causa" "$(run) [$(cat "$TMP/detail")]" "0 []"
ok "imprime el informe JSON" "$(grep -c 'classify_enforce_done.*"hidden": 3' "$TMP/out")" "1"
ok "pide --notify a enforce" "$(grep -c -- '--notify' "$TMP/docker.args")" "1"

: > "$TMP/detail"; run --max-change-pct 25 --dry-run > /dev/null
ok "pasa los argumentos a enforce" "$(grep -c -- '--max-change-pct 25 --dry-run' "$TMP/docker.args")" "1"

: > "$TMP/detail"; export STUB_MODE=cap
ok "tope superado: sale 4" "$(run)" "4"
ok "la causa del tope va al aviso" "$(grep -c 'cambio masivo bloqueado' "$TMP/detail")" "1"

: > "$TMP/detail"; export STUB_MODE=boom
ok "otro fallo: propaga el código" "$(run)" "2"
ok "la causa incluye el código y el error" "$(grep -c 'código 2.*kaboom' "$TMP/detail")" "1"

echo
if [[ "$FAILS" -eq 0 ]]; then echo "OK"; else echo "$FAILS fallo(s)"; exit 1; fi
