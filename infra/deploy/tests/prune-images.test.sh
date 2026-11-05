#!/usr/bin/env bash
# Pruebas de prune-images.sh con un `docker` simulado: no toca imágenes reales.
#   bash infra/deploy/tests/prune-images.test.sh
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/../prune-images.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin"
CALLS="$TMP/calls.log"
FAILS=0

# docker simulado: `image ls <repo>` devuelve $TMP/images/<repo con / -> _>; `rmi` anota la llamada.
cat > "$TMP/bin/docker" <<'STUB'
#!/usr/bin/env bash
case "$1 $2" in
  "image ls")
    f="$STUB_DIR/images/${3//\//_}"
    [[ -f "$f" ]] && cat "$f"
    ;;
  "rmi "*|"rmi")
    echo "rmi $2" >> "$STUB_CALLS"
    [[ " ${STUB_IN_USE:-} " == *" $2 "* ]] && exit 1
    exit 0
    ;;
esac
STUB
chmod +x "$TMP/bin/docker"
export PATH="$TMP/bin:$PATH" STUB_DIR="$TMP" STUB_CALLS="$CALLS"

# fixture: <repo> <fecha> <tag> ...
image() { # repo "fecha" tag
  mkdir -p "$TMP/images"
  printf '%s\t%s\n' "$2" "$3" >> "$TMP/images/${1//\//_}"
}
reset() { rm -rf "$TMP/images" "$CALLS"; touch "$CALLS"; unset STUB_IN_USE KEEP_IMAGES; }
ok() { if [[ "$2" == "$3" ]]; then echo "  ok   - $1"; else echo "  FAIL - $1"; echo "         esperado: $3"; echo "         obtenido: $2"; FAILS=$((FAILS + 1)); fi; }
calls() { sort "$CALLS" | tr '\n' ' ' | sed 's/ $//'; }

echo "keeps the 3 newest and removes the rest (ordered by date, not by SHA)"
reset
image radio-gofestivals/api "2026-11-05 11:00:00 +0000 UTC" ffffff1   # el SHA mayor, pero el más antiguo
image radio-gofestivals/api "2026-11-05 12:00:00 +0000 UTC" 1111111
image radio-gofestivals/api "2026-11-05 13:00:00 +0000 UTC" 2222222
image radio-gofestivals/api "2026-11-05 14:00:00 +0000 UTC" 3333333
image radio-gofestivals/api "2026-11-05 15:00:00 +0000 UTC" 4444444
bash "$SCRIPT" >/dev/null
ok "removes the two oldest" "$(calls)" "rmi radio-gofestivals/api:1111111 rmi radio-gofestivals/api:ffffff1"

echo "does nothing when there are 3 or fewer"
reset
for t in aaaaaaa bbbbbbb ccccccc; do image radio-gofestivals/web "2026-11-05 1$((RANDOM % 9)):00:00 +0000 UTC" "$t"; done
bash "$SCRIPT" >/dev/null
ok "no rmi calls" "$(calls)" ""

echo "never touches latest or non-SHA tags"
reset
image radio-gofestivals/web "2026-11-01 10:00:00 +0000 UTC" latest
image radio-gofestivals/web "2026-11-01 10:00:00 +0000 UTC" dev
image radio-gofestivals/web "2026-11-01 10:00:00 +0000 UTC" v1.2.3
image radio-gofestivals/web "2026-11-01 10:00:00 +0000 UTC" 12345       # demasiado corto para un SHA
image radio-gofestivals/web "2026-11-01 10:00:00 +0000 UTC" GGGGGGG     # no es hex
for i in 1 2 3 4; do image radio-gofestivals/web "2026-11-0$((i+1)) 10:00:00 +0000 UTC" "abcdef$i"; done
bash "$SCRIPT" >/dev/null
ok "only the oldest SHA tag" "$(calls)" "rmi radio-gofestivals/web:abcdef1"

echo "each service is pruned independently"
reset
for svc in api web icy-worker scripts; do
  for i in 1 2 3 4; do image "radio-gofestivals/$svc" "2026-11-0$i 10:00:00 +0000 UTC" "00000$i$i"; done
done
bash "$SCRIPT" >/dev/null
ok "one oldest tag per service" "$(calls)" "rmi radio-gofestivals/api:0000011 rmi radio-gofestivals/icy-worker:0000011 rmi radio-gofestivals/scripts:0000011 rmi radio-gofestivals/web:0000011"

echo "dry-run reports but never removes"
reset
for i in 1 2 3 4 5; do image radio-gofestivals/api "2026-11-0$i 10:00:00 +0000 UTC" "ab0000$i"; done
out="$(bash "$SCRIPT" --dry-run)"
ok "no rmi calls" "$(calls)" ""
ok "lists what it would remove" "$(grep -c '^would remove' <<<"$out")" "2"
ok "summary says would remove" "$(grep -c 'would remove 2 image' <<<"$out")" "1"

echo "an image in use is skipped and the rest continue"
reset
for i in 1 2 3 4 5; do image radio-gofestivals/api "2026-11-0$i 10:00:00 +0000 UTC" "ab0000$i"; done
export STUB_IN_USE="radio-gofestivals/api:ab00001"
out="$(bash "$SCRIPT")"
ok "tried both old tags" "$(calls)" "rmi radio-gofestivals/api:ab00001 rmi radio-gofestivals/api:ab00002"
ok "reports the one in use" "$(grep -c 'kept (in use) radio-gofestivals/api:ab00001' <<<"$out")" "1"
ok "reports the removed one" "$(grep -c '^removed radio-gofestivals/api:ab00002' <<<"$out")" "1"
ok "still exits 0" "$(bash "$SCRIPT" >/dev/null; echo $?)" "0"

echo "KEEP_IMAGES overrides the default"
reset
for i in 1 2 3 4 5; do image radio-gofestivals/api "2026-11-0$i 10:00:00 +0000 UTC" "ab0000$i"; done
KEEP_IMAGES=1 bash "$SCRIPT" >/dev/null
ok "keeps only the newest" "$(calls)" "rmi radio-gofestivals/api:ab00001 rmi radio-gofestivals/api:ab00002 rmi radio-gofestivals/api:ab00003 rmi radio-gofestivals/api:ab00004"

echo "invalid KEEP_IMAGES removes nothing (a typo must not wipe the images)"
for bad in 0 -1 abc "" " "; do
  reset
  for i in 1 2 3 4 5; do image radio-gofestivals/api "2026-11-0$i 10:00:00 +0000 UTC" "ab0000$i"; done
  KEEP_IMAGES="$bad" bash "$SCRIPT" >/dev/null 2>&1
  if [[ -z "$bad" || "$bad" == " " ]]; then
    ok "KEEP_IMAGES='$bad' behaves (empty -> default 3)" "$(grep -c rmi "$CALLS" || true)" "$([[ -z "$bad" ]] && echo 2 || echo 0)"
  else
    ok "KEEP_IMAGES='$bad' removes nothing" "$(calls)" ""
  fi
done

echo "a repository without images is fine"
reset
bash "$SCRIPT" >/dev/null
ok "no calls and exit 0" "$(calls)|$?" "|0"

echo
if (( FAILS )); then echo "FALLARON $FAILS comprobaciones"; exit 1; fi
echo "todas las comprobaciones pasan"
