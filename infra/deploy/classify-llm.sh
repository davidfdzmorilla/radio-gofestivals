#!/usr/bin/env bash
# =============================================================================
# classify-llm.sh — segundo clasificador "¿es electrónica?" (ADR 012, Fase 2).
#
# Toma las emisoras que las reglas no resuelven (banda `review` y curadas que las reglas
# rechazarían), las pasa por `claude -p` en lotes y guarda los veredictos con
# `classify-stations apply-llm`. Por ahora en modo sombra: nada oculta emisoras.
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
APPLY_FLAGS=()
[[ "${CLASSIFY_LLM_DRY_RUN:-0}" == "1" ]] && APPLY_FLAGS=(--dry-run)

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

if ! "${COMPOSE[@]}" run --rm -T scripts classify-stations review-export --limit "$LIMIT" \
  > "$WORK/export.json" 2> "$WORK/export.err"; then
  echo "classify-llm: fallo al exportar candidatas: $(tail -c 300 "$WORK/export.err")" >&2
  exit 1
fi

# Parte la lista en lotes: $WORK/batch-<n>.json con {"stations":[...]}; imprime cuántos hay.
n_batches="$(python3 - "$WORK" "$BATCH" <<'PY'
import json, sys
work, size = sys.argv[1], int(sys.argv[2])
try:
    stations = json.load(open(f"{work}/export.json"))["stations"]
except Exception as exc:  # noqa: BLE001
    print(f"error: {exc}", file=sys.stderr)
    sys.exit(1)
chunks = [stations[i:i + size] for i in range(0, len(stations), size)]
for n, chunk in enumerate(chunks, 1):
    json.dump({"stations": chunk}, open(f"{work}/batch-{n}.json", "w"), ensure_ascii=False)
print(len(chunks))
PY
)" || { echo "classify-llm: la exportación no es un JSON válido" >&2; exit 1; }

if [[ "$n_batches" == "0" ]]; then
  echo '{"event":"classify_llm_done","candidates":0,"batches":0}'
  exit 0
fi

PROMPT="$(cat "$HERE/classify-llm/prompt.txt")"
SCHEMA="$(cat "$HERE/classify-llm/schema.json")"
failed=0
done_batches=0
echo '{"results":[]}' > "$WORK/results.json"

for ((i = 1; i <= n_batches; i++)); do
  input="$(cat "$WORK/batch-$i.json")"
  if ! (cd "$WORK/empty" && timeout "$TIMEOUT_S" "$CLAUDE_BIN" -p "$PROMPT

EMISORAS:
$input" --model "$MODEL" --tools "" --strict-mcp-config --disable-slash-commands \
    --output-format json --json-schema "$SCHEMA" --no-session-persistence \
    < /dev/null > "$WORK/out-$i.json" 2> "$WORK/err-$i.txt"); then
    echo "classify-llm: lote $i/$n_batches: claude falló: $(tail -c 300 "$WORK/err-$i.txt")" >&2
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
    echo "classify-llm: lote $i/$n_batches: respuesta inválida o con error" >&2
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
    echo "classify-llm: fallo al guardar veredictos" >&2
    exit 1
  fi
fi

echo "{\"event\":\"classify_llm_done\",\"batches\":$n_batches,\"batches_ok\":$done_batches,\"failed\":$failed,\"apply\":${apply_out:-null}}"
[[ "$failed" -eq 0 ]] && exit 0
exit 3
