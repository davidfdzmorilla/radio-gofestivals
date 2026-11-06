#!/usr/bin/env bash
# =============================================================================
# classify-llm.sh — segundo clasificador "¿es electrónica?" (ADR 012, Fase 2).
#
# Toma las emisoras que las reglas no resuelven (banda `review` y curadas que las reglas
# rechazarían), les añade la web de la emisora y sus últimos temas (medido el 2026-11-06: baja las
# dudosas del 52 % al 41 % y corrige errores del juicio solo por nombre y tags), las pasa por
# `claude -p` en lotes y guarda los veredictos con `classify-stations apply-llm`.
# Por ahora en modo sombra: nada oculta emisoras.
#
# Usa la sesión de suscripción de Claude Code del usuario que ejecuta el cron (decisión de
# David: sin gasto de API). Por eso:
#   - se retiran ANTHROPIC_API_KEY/AUTH_TOKEN del entorno: con clave presente `claude -p`
#     facturaría por API sin avisar;
#   - NO se usa --bare (no lee la suscripción) y se ejecuta desde un directorio vacío para que
#     no cargue ningún CLAUDE.md; --strict-mcp-config y --disable-slash-commands recortan el
#     contexto de ~160.000 a ~5.000 tokens por llamada (medido el 2026-11-06);
#   - sin herramientas (--tools ""): el texto de las emisoras es de terceros y el modelo no
#     puede actuar, solo devolver el JSON del esquema.
# Al primer fallo (límite de uso, sesión caducada, JSON inválido) se corta: los lotes ya
# resueltos se guardan, el resto queda para la siguiente ejecución, y el código de salida != 0
# hace que run-job.sh avise por Telegram.
#
#   CLASSIFY_LLM_LIMIT    emisoras por ejecución        (120)
#   CLASSIFY_LLM_BATCH    emisoras por llamada          (40)
#   CLASSIFY_LLM_MODEL    alias o nombre de modelo      (haiku)
#   CLASSIFY_LLM_TIMEOUT  segundos por llamada          (300)
#   CLAUDE_BIN            ejecutable de claude          (claude)
#   CLASSIFY_LLM_DRY_RUN  1 = llama al modelo pero apply-llm solo cuenta, no escribe
#   CLASSIFY_LLM_HEARTBEAT fichero que se toca al terminar bien (/var/log/radio/classify-llm.last-ok);
#                         watchdog.sh avisa si lleva más de 36 h sin tocarse
#
# Alertas: ante cualquier fallo deja la causa en $RUN_JOB_DETAIL_FILE (la añade run-job.sh al aviso
# de Telegram); al terminar bien cierra el aviso abierto con un mensaje de recuperación.
# Salida: 0 ok (o nada que hacer) · 1 fallo previo a clasificar · 3 algún lote falló.
# =============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
LIMIT="${CLASSIFY_LLM_LIMIT:-120}"
BATCH="${CLASSIFY_LLM_BATCH:-40}"
MODEL="${CLASSIFY_LLM_MODEL:-haiku}"
TIMEOUT_S="${CLASSIFY_LLM_TIMEOUT:-300}"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"
HEARTBEAT="${CLASSIFY_LLM_HEARTBEAT:-/var/log/radio/classify-llm.last-ok}"
APPLY_FLAGS=()
DRY_RUN=0
[[ "${CLASSIFY_LLM_DRY_RUN:-0}" == "1" ]] && { APPLY_FLAGS=(--dry-run); DRY_RUN=1; }

# Deja la causa del fallo para el aviso de run-job.sh (y en stderr, que va al log).
fail_detail() {
  echo "classify-llm: $1" >&2
  [[ -n "${RUN_JOB_DETAIL_FILE:-}" ]] && printf '%s\n' "$1" > "$RUN_JOB_DETAIL_FILE"
  return 0
}

# Traduce la salida de claude a una causa legible. Es heurística: el texto exacto de los
# errores de `claude -p` (límite de uso, sesión caducada) no está documentado, así que siempre se
# adjunta además un extracto literal.
explain_failure() { # rc archivos...
  local rc="$1"; shift
  local blob excerpt cause
  blob="$(cat "$@" 2> /dev/null | tr '\n' ' ' | head -c 2000)"
  excerpt="$(printf '%s' "$blob" | head -c 160)"
  if [[ "$rc" == "124" ]]; then
    cause="claude no respondió en ${TIMEOUT_S}s"
  elif [[ "${blob,,}" =~ (session\ limit|weekly\ limit|usage\ limit|rate\ limit|limit\ reached|hit\ your) ]]; then
    cause="límite de uso de la suscripción (se reintenta en la siguiente ejecución)"
  elif [[ "${blob,,}" =~ (not\ logged\ in|/login|authenticat|unauthorized|401|expired|revoked|credential) ]]; then
    cause="sesión de Claude caducada o sin iniciar: ejecuta 'claude' y /login (o 'claude setup-token')"
  else
    cause="error de claude (código ${rc}) o respuesta inválida"
  fi
  printf '%s%s' "$cause" "${excerpt:+ · «${excerpt}»}"
}

# Ejecución correcta: latido para watchdog.sh y cierre del aviso abierto. No en ensayo.
finish_ok() {
  [[ "$DRY_RUN" == "1" ]] && return 0
  mkdir -p "$(dirname "$HEARTBEAT")" 2> /dev/null && touch "$HEARTBEAT" 2> /dev/null
  for key in cron:classify-llm classify-llm-stale; do
    "${COMPOSE[@]}" run --rm -T --no-deps scripts watchdog resolve --key "$key" \
      --message "classify-llm vuelve a funcionar" > /dev/null 2>&1 || true
  done
  return 0
}

# cron arranca con un PATH mínimo (/usr/bin:/bin) y claude suele vivir en ~/.nvm o ~/.local/bin:
# si no resuelve con el PATH actual se busca ahí (el nvm más reciente) y, si no está, se falla
# pronto y claro en vez de a mitad de la ejecución.
if ! command -v "$CLAUDE_BIN" > /dev/null 2>&1; then
  for candidate in \
    "$(ls -d "$HOME"/.nvm/versions/node/*/bin/claude 2> /dev/null | sort -V | tail -n 1)" \
    "$HOME/.local/bin/claude" "/usr/local/bin/claude"; do
    if [[ -n "$candidate" && -x "$candidate" ]]; then
      CLAUDE_BIN="$candidate"
      break
    fi
  done
fi
if ! command -v "$CLAUDE_BIN" > /dev/null 2>&1; then
  fail_detail "no se encuentra 'claude' (PATH=$PATH). Instálalo o define CLAUDE_BIN."
  exit 1
fi

for v in LIMIT BATCH TIMEOUT_S; do
  if ! [[ "${!v}" =~ ^[1-9][0-9]*$ ]]; then
    echo "classify-llm: $v debe ser un entero >= 1 (valor: '${!v}')" >&2
    exit 1
  fi
done

unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN
cd "$REPO" || exit 1
COMPOSE=(docker compose --env-file .env.production -f docker-compose.prod.yml)
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/empty"

if ! "${COMPOSE[@]}" run --rm -T scripts classify-stations review-export --limit "$LIMIT" --with-evidence \
  > "$WORK/export.json" 2> "$WORK/export.err"; then
  fail_detail "fallo al exportar candidatas: $(tail -c 300 "$WORK/export.err")"
  exit 1
fi

# Parte la lista en lotes: $WORK/batch-<n>.json con {"stations":[...]}; imprime cuántos hay.
# Cada lote lleva como máximo BATCH emisoras y ~100 KB: el prompt viaja como argumento de
# `claude -p` y Linux limita un argumento a 128 KB (con web y temas cada emisora pesa ~1-2 KB).
n_batches="$(python3 - "$WORK" "$BATCH" <<'PY'
import json, sys
MAX_BYTES = 100_000
work, size = sys.argv[1], int(sys.argv[2])
try:
    # El JSON es la línea {"stations": ...}; ignora cualquier otra línea de log en stdout.
    lines = [ln for ln in open(f"{work}/export.json") if ln.startswith('{"stations"')]
    stations = json.loads(lines[-1])["stations"]
except Exception as exc:  # noqa: BLE001
    print(f"error: {exc}", file=sys.stderr)
    sys.exit(1)
chunks, current, weight = [], [], 0
for st in stations:
    w = len(json.dumps(st, ensure_ascii=False).encode())
    if current and (len(current) >= size or weight + w > MAX_BYTES):
        chunks.append(current)
        current, weight = [], 0
    current.append(st)
    weight += w
if current:
    chunks.append(current)
for n, chunk in enumerate(chunks, 1):
    json.dump({"stations": chunk}, open(f"{work}/batch-{n}.json", "w"), ensure_ascii=False)
print(len(chunks))
PY
)" || { fail_detail "la exportación no es un JSON válido"; exit 1; }

if [[ "$n_batches" == "0" ]]; then
  echo '{"event":"classify_llm_done","candidates":0,"batches":0}'
  finish_ok
  exit 0
fi

PROMPT="$(cat "$HERE/classify-llm/prompt.txt")"
SCHEMA="$(cat "$HERE/classify-llm/schema.json")"
failed=0
done_batches=0
echo '{"results":[]}' > "$WORK/results.json"

for ((i = 1; i <= n_batches; i++)); do
  input="$(cat "$WORK/batch-$i.json")"
  (cd "$WORK/empty" && timeout "$TIMEOUT_S" "$CLAUDE_BIN" -p "$PROMPT

EMISORAS:
$input" --model "$MODEL" --tools "" --strict-mcp-config --disable-slash-commands \
    --output-format json --json-schema "$SCHEMA" --no-session-persistence \
    < /dev/null > "$WORK/out-$i.json" 2> "$WORK/err-$i.txt")
  claude_rc=$?
  if [[ "$claude_rc" -ne 0 ]]; then
    fail_detail "lote $i/$n_batches: $(explain_failure "$claude_rc" "$WORK/err-$i.txt" "$WORK/out-$i.json")"
    failed=1
    break
  fi
  # Acepta solo una respuesta sin error y con structured_output.results (lista de objetos).
  if ! python3 - "$WORK" "$i" <<'PY'
import json, sys
work, i = sys.argv[1], sys.argv[2]
env = json.load(open(f"{work}/out-{i}.json"))
res = (env.get("structured_output") or {}).get("results")
if env.get("is_error") or not isinstance(res, list):
    print(f"error: is_error={env.get('is_error')} result={str(env.get('result'))[:200]}", file=sys.stderr)
    sys.exit(1)
acc = json.load(open(f"{work}/results.json"))
acc["results"].extend(r for r in res if isinstance(r, dict))
json.dump(acc, open(f"{work}/results.json", "w"), ensure_ascii=False)
PY
  then
    fail_detail "lote $i/$n_batches: $(explain_failure 0 "$WORK/out-$i.json")"
    failed=1
    break
  fi
  done_batches=$((done_batches + 1))
done

# Guarda lo que sí se resolvió, aunque un lote posterior fallara.
apply_out=""
if [[ "$done_batches" -gt 0 ]]; then
  if ! apply_out="$("${COMPOSE[@]}" run --rm -T scripts classify-stations apply-llm "${APPLY_FLAGS[@]}" \
    < "$WORK/results.json" 2>&1 | grep apply_llm_done)"; then
    fail_detail "fallo al guardar veredictos (apply-llm)"
    exit 1
  fi
fi

echo "{\"event\":\"classify_llm_done\",\"batches\":$n_batches,\"batches_ok\":$done_batches,\"failed\":$failed,\"apply\":${apply_out:-null}}"
if [[ "$failed" -eq 0 ]]; then
  finish_ok
  exit 0
fi
exit 3
