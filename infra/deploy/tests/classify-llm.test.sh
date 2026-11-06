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
  echo "$*" > "$STUB_DIR/export.args"
  [[ -n "${STUB_EXPORT_FAIL:-}" ]] && { echo "boom" >&2; exit 1; }
  cat "$STUB_DIR/export.json"
elif [[ " $* " == *" watchdog resolve "* ]]; then
  echo "$*" | sed 's/.*--key \([^ ]*\).*/\1/' >> "$STUB_DIR/resolve.calls"
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
[[ "$mode" == "auth" ]] && { echo "Not logged in · Please run /login" >&2; exit 1; }
[[ "$mode" == "timeout" ]] && exit 124
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
msg = "Your weekly limit resets Mon 12:00am" if mode == "weekly" else "You've hit your session limit · resets 3:45pm"
env = {"is_error": mode in ("is_error", "weekly"), "result": msg, "structured_output": {"results": res}}
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
reset() { rm -f "$TMP"/{export.args,claude.count,claude.calls,applied.json,apply.args,resolve.calls,hb,detail,old-claude-used}; : > "$TMP/detail"; unset STUB_EXPORT_FAIL STUB_CLAUDE_MODE ANTHROPIC_API_KEY CLASSIFY_LLM_DRY_RUN; }
ok() { if [[ "$2" == "$3" ]]; then echo "  ok   - $1"; else echo "  FAIL - $1"; echo "         esperado: $3"; echo "         obtenido: $2"; FAILS=$((FAILS + 1)); fi; }
calls() { cat "$TMP/claude.count" 2>/dev/null || echo 0; }
applied_slugs() { python3 -c "import json;print(','.join(r['slug'] for r in json.load(open('$TMP/applied.json'))['results']))" 2>/dev/null || echo "-"; }
run() { RUN_JOB_DETAIL_FILE="$TMP/detail" CLASSIFY_LLM_HEARTBEAT="$TMP/hb" CLASSIFY_LLM_BATCH="${BATCH:-2}" bash "$SCRIPT" >"$TMP/out.txt" 2>"$TMP/err.txt"; echo $?; }

echo "classify-llm.sh"

reset; stations 5
ok "5 candidatas en lotes de 2 -> 3 llamadas, sale 0" "$(run) $(calls)" "0 3"
ok "se guardan los 5 veredictos juntos" "$(applied_slugs)" "s1,s2,s3,s4,s5"

reset; stations 3
{ echo 'HTTP Request: GET https://x.example/ "HTTP/1.1 200 OK"'; cat "$TMP/export.json"; echo '{"event": "ruido", "level": "info"}'; } > "$TMP/export2.json" && mv "$TMP/export2.json" "$TMP/export.json"
ok "líneas de log en stdout alrededor del JSON no rompen la exportación" "$(run) $(calls)" "0 2"
ok "y se guardan las 3 emisoras" "$(applied_slugs)" "s1,s2,s3"

reset; stations 2; run >/dev/null
ok "pide la evidencia (web y temas) al exportar" "$(grep -c -- '--with-evidence' "$TMP/export.args")" "1"
ok "el prompt incluye la guía de web y últimos temas" "$(grep -c 'ultimos_temas' "$HERE/../classify-llm/prompt.txt")" "1"

# lotes por tamaño: 6 emisoras de ~40 KB con BATCH=40 no caben juntas en un argumento de claude
reset
python3 - > "$TMP/export.json" <<'PY'
import json
print(json.dumps({"stations": [{"slug": f"big{i}", "name": "B", "country": "ES", "tags": ["house"], "web": {"description": "x" * 40000}} for i in range(1, 7)]}))
PY
ok "lotes acotados por tamaño (6 emisoras de 40 KB, 2 por lote -> 3 llamadas)" "$(BATCH=40 run) $(calls)" "0 3"
ok "no se pierde ninguna emisora al partir por tamaño" "$(applied_slugs)" "big1,big2,big3,big4,big5,big6"

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
echo "alertas y latido"
detail() { tr -d '\n' < "$TMP/detail"; }
has() { [[ "$(detail)" == *"$1"* ]] && echo si || echo no; }

reset; stations 2; export STUB_CLAUDE_MODE=is_error; run >/dev/null
ok "límite de uso: la causa lo dice y lleva extracto" "$(has 'límite de uso') $(has 'session limit')" "si si"
reset; stations 2; export STUB_CLAUDE_MODE=weekly; run >/dev/null
ok "límite semanal (otra redacción): también se reconoce" "$(has 'límite de uso')" "si"
reset; stations 2; export STUB_CLAUDE_MODE=auth; run >/dev/null
ok "sesión caducada: la causa indica cómo arreglarlo" "$(has 'sesión de Claude caducada') $(has '/login')" "si si"
reset; stations 2; export STUB_CLAUDE_MODE=timeout; run >/dev/null
ok "timeout: la causa lo dice" "$(has 'no respondió')" "si"
reset; stations 2; export STUB_CLAUDE_MODE=no_structured; run >/dev/null
ok "respuesta sin structured_output: causa genérica con lote" "$(has 'lote 1/1')" "si"
reset; stations 2; export STUB_EXPORT_FAIL=1; run >/dev/null
ok "fallo al exportar: la causa lo dice" "$(has 'fallo al exportar')" "si"
reset; echo "nada" > "$TMP/export.json"; run >/dev/null
ok "exportación inválida: la causa lo dice" "$(has 'no es un JSON válido')" "si"

reset; stations 2; run >/dev/null
ok "éxito: toca el latido" "$([[ -f $TMP/hb ]] && echo si || echo no)" "si"
ok "éxito: cierra los dos avisos abiertos" "$(sort "$TMP/resolve.calls" | tr '\n' ' ')" "classify-llm-stale cron:classify-llm "
ok "éxito: no deja causa de fallo" "$(detail)" ""
reset; stations 0; run >/dev/null
ok "sin candidatas también cuenta como ejecución correcta (latido)" "$([[ -f $TMP/hb ]] && echo si || echo no)" "si"
reset; stations 2; export STUB_CLAUDE_MODE=is_error; run >/dev/null
ok "fallo: no toca el latido ni cierra avisos" "$([[ -f $TMP/hb ]] && echo si || echo no) $([[ -f $TMP/resolve.calls ]] && echo si || echo no)" "no no"
reset; stations 2; export CLASSIFY_LLM_DRY_RUN=1; run >/dev/null
ok "ensayo: no toca el latido ni cierra avisos" "$([[ -f $TMP/hb ]] && echo si || echo no) $([[ -f $TMP/resolve.calls ]] && echo si || echo no)" "no no"

# claude fuera del PATH (como en cron): se busca en ~/.nvm y, si no está, falla pronto con 1.
reset; stations 2
fakehome="$TMP/home"; mkdir -p "$fakehome/.nvm/versions/node/v20.1.0/bin" "$fakehome/.nvm/versions/node/v24.2.0/bin"
cp "$TMP/bin/claude" "$fakehome/.nvm/versions/node/v24.2.0/bin/claude"
echo '#!/usr/bin/env bash
echo OLD >> "$STUB_DIR/old-claude-used"; exit 1' > "$fakehome/.nvm/versions/node/v20.1.0/bin/claude"; chmod +x "$fakehome/.nvm/versions/node/v20.1.0/bin/claude"
nopath="$TMP/nopath"; mkdir -p "$nopath"; ln -sf "$TMP/bin/docker" "$nopath/docker"
for t in bash python3 timeout cat ls sort tail mktemp rm mkdir dirname grep tr head; do ln -sf "$(command -v $t)" "$nopath/$t"; done
out="$(HOME="$fakehome" PATH="$nopath" CLASSIFY_LLM_BATCH=2 bash "$SCRIPT" 2>&1 >/dev/null; echo "rc=$?")"
ok "claude fuera del PATH: lo encuentra en ~/.nvm (el más reciente) y sale 0" "$(echo "$out" | grep -c 'rc=0') $(calls) $([[ -f $TMP/old-claude-used ]] && echo viejo || echo nuevo)" "1 1 nuevo"
reset; stations 2
out="$(HOME="$TMP/nohome" PATH="$nopath" bash "$SCRIPT" 2>&1; echo "rc=$?")"
ok "sin claude en ningún sitio: falla pronto con 1 y mensaje claro" "$(echo "$out" | grep -c 'no se encuentra .claude.') $(echo "$out" | grep -c 'rc=1') $(calls)" "1 1 0"
reset; stations 2
HOME="$TMP/nohome" PATH="$nopath" RUN_JOB_DETAIL_FILE="$TMP/detail" bash "$SCRIPT" >/dev/null 2>&1
ok "sin claude: deja la causa para el aviso" "$(has "no se encuentra 'claude'")" "si"

echo
if [[ "$FAILS" -eq 0 ]]; then echo "OK"; else echo "$FAILS fallo(s)"; exit 1; fi
