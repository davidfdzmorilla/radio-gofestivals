#!/usr/bin/env bash
# Pruebas de classify-llm.sh con `docker` y `claude` simulados: no toca la base ni gasta cuota.
#   bash infra/deploy/tests/classify-llm.test.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/../classify-llm.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin"
FAILS=0

# docker simulado: review-export devuelve $TMP/export.json; apply-llm guarda su stdin.
cat > "$TMP/bin/docker" <<'STUB'
#!/usr/bin/env bash
if [[ " $* " == *" review-export "* ]]; then
  [[ -n "${STUB_EXPORT_FAIL:-}" ]] && { echo "boom" >&2; exit 1; }
  cat "$STUB_DIR/export.json"
elif [[ " $* " == *" apply-llm "* ]]; then
  echo "$*" > "$STUB_DIR/apply.args"
  cat > "$STUB_DIR/applied.json"
  echo '{"applied": 1, "event": "apply_llm_done"}'
fi
STUB
# claude simulado: anota argumentos, entorno y cwd; responde según STUB_CLAUDE_MODE.
cat > "$TMP/bin/claude" <<'STUB'
#!/usr/bin/env bash
n=$(( $(cat "$STUB_DIR/claude.count" 2>/dev/null || echo 0) + 1 ))
echo "$n" > "$STUB_DIR/claude.count"
{ echo "cwd=$PWD"; echo "key=${ANTHROPIC_API_KEY:-<unset>}"; echo "args=$*" | tr '\n' ' '; echo; } >> "$STUB_DIR/claude.calls"
mode="${STUB_CLAUDE_MODE:-ok}"
[[ "$mode" == "fail_on_2" && "$n" -eq 2 ]] && { echo "limit reached" >&2; exit 1; }
[[ "$mode" == "always_fail" ]] && exit 1
args="$*"
slugs=$(python3 - "$args" <<'PY'
import re, sys
print(" ".join(re.findall(r'"slug": ?"([^"]+)"', sys.argv[1])))
PY
)
python3 - "$mode" $slugs <<'PY'
import json, sys
mode, slugs = sys.argv[1], sys.argv[2:]
res = [{"slug": s, "verdict": "electronic", "confidence": 90, "reason": "r"} for s in slugs]
env = {"is_error": mode == "is_error", "result": "You've hit your session limit", "structured_output": {"results": res}}
if mode == "no_structured":
    env.pop("structured_output")
print(json.dumps(env))
PY
STUB
chmod +x "$TMP/bin/docker" "$TMP/bin/claude"
export PATH="$TMP/bin:$PATH" STUB_DIR="$TMP"

stations() { # n -> {"stations":[{slug:s1},...]}
  python3 - "$1" > "$TMP/export.json" <<'PY'
import json, sys
n = int(sys.argv[1])
print(json.dumps({"stations": [{"slug": f"s{i}", "name": f"S {i}", "country": "ES", "tags": ["house"]} for i in range(1, n + 1)]}))
PY
}
reset() { rm -f "$TMP"/{claude.count,claude.calls,applied.json,apply.args}; unset STUB_EXPORT_FAIL STUB_CLAUDE_MODE ANTHROPIC_API_KEY CLASSIFY_LLM_DRY_RUN; }
ok() { if [[ "$2" == "$3" ]]; then echo "  ok   - $1"; else echo "  FAIL - $1"; echo "         esperado: $3"; echo "         obtenido: $2"; FAILS=$((FAILS + 1)); fi; }
calls() { cat "$TMP/claude.count" 2>/dev/null || echo 0; }
applied_slugs() { python3 -c "import json;print(','.join(r['slug'] for r in json.load(open('$TMP/applied.json'))['results']))" 2>/dev/null || echo "-"; }
run() { CLASSIFY_LLM_BATCH="${BATCH:-2}" bash "$SCRIPT" >"$TMP/out.txt" 2>"$TMP/err.txt"; echo $?; }

echo "classify-llm.sh"

reset; stations 5
ok "5 candidatas en lotes de 2 -> 3 llamadas, sale 0" "$(run) $(calls)" "0 3"
ok "se guardan los 5 veredictos juntos" "$(applied_slugs)" "s1,s2,s3,s4,s5"

reset; stations 0
ok "sin candidatas no llama a claude ni a apply" "$(run) $(calls) $([[ -f $TMP/applied.json ]] && echo applied || echo none)" "0 0 none"

reset; stations 6; export STUB_CLAUDE_MODE=fail_on_2
ok "fallo en el lote 2: corta y sale 3" "$(run) $(calls)" "3 2"
ok "guarda solo lo ya resuelto (lote 1)" "$(applied_slugs)" "s1,s2"

reset; stations 4; export STUB_CLAUDE_MODE=is_error
ok "respuesta con is_error: sale 3 y no guarda nada" "$(run) $([[ -f $TMP/applied.json ]] && echo applied || echo none)" "3 none"

reset; stations 4; export STUB_CLAUDE_MODE=no_structured
ok "sin structured_output: sale 3 y no guarda nada" "$(run) $([[ -f $TMP/applied.json ]] && echo applied || echo none)" "3 none"

reset; stations 2; export STUB_EXPORT_FAIL=1
ok "fallo al exportar: sale 1 sin llamar a claude" "$(run) $(calls)" "1 0"

reset; echo "no es json" > "$TMP/export.json"
ok "exportación inválida: sale 1" "$(run) $(calls)" "1 0"

reset; stations 2; export ANTHROPIC_API_KEY=sk-secret
run >/dev/null
ok "retira ANTHROPIC_API_KEY (no facturar por API)" "$(grep -c 'key=<unset>' "$TMP/claude.calls")" "1"

reset; stations 2
run >/dev/null
ok "se ejecuta desde un directorio vacío, no desde el repo" "$(grep -c 'cwd=.*/empty' "$TMP/claude.calls")" "1"
flags="$(cat "$TMP/claude.calls")"
for f in '--tools ' '--strict-mcp-config' '--disable-slash-commands' '--no-session-persistence' '--json-schema' '--model haiku'; do
  ok "pasa $f" "$([[ "$flags" == *"$f"* ]] && echo si || echo no)" "si"
done
ok "no usa --bare (no lee la suscripción)" "$([[ "$flags" == *"--bare"* ]] && echo si || echo no)" "no"

reset; stations 2; run >/dev/null
ok "por defecto apply-llm escribe (sin --dry-run)" "$(grep -c -- '--dry-run' "$TMP/apply.args")" "0"
reset; stations 2; export CLASSIFY_LLM_DRY_RUN=1; run >/dev/null
ok "CLASSIFY_LLM_DRY_RUN=1 pasa --dry-run a apply-llm" "$(grep -c -- '--dry-run' "$TMP/apply.args")" "1"

reset; stations 2
ok "CLASSIFY_LLM_BATCH inválido: sale 1" "$(CLASSIFY_LLM_BATCH=abc bash "$SCRIPT" >/dev/null 2>&1; echo $?)" "1"

echo
if [[ "$FAILS" -eq 0 ]]; then echo "OK"; else echo "$FAILS fallo(s)"; exit 1; fi
