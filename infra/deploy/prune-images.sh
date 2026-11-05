#!/usr/bin/env bash
# =============================================================================
# prune-images.sh [--dry-run] — conserva las últimas N versiones de las imágenes
# radio-gofestivals/* y borra las anteriores.
#
# Cada deploy construye api, web, icy-worker y scripts con el tag del SHA de git y
# `docker image prune` solo borra imágenes huérfanas, así que los tags viejos se acumulan
# (60 tras ~15 deploys). Medido el 2026-11-05: las versiones comparten casi todas sus capas, así
# que borrarlos libera poco espacio real (< 0,1 GB); las imágenes de la radio suman ~1 GB únicos.
# Es higiene (listas de imágenes manejables, sin versiones inservibles), NO la solución a un
# disco lleno: el grueso del VPS son imágenes y volúmenes de otros proyectos.
#
#   KEEP_IMAGES   versiones a conservar por servicio (por defecto 3: la actual y las 2
#                 anteriores). El rollback de deploy.sh usa IDs de imagen y no depende
#                 de los tags, pero conviene dejar margen para un rollback manual.
#
# Solo toca tags que parecen un SHA de git (7-40 hex). Nunca `latest`, nunca otros
# repositorios. Docker se niega a borrar una imagen usada por un contenedor: se informa y
# se sigue. Es best-effort: termina siempre con código 0 (un fallo aquí no debe fallar un
# deploy ya hecho).
# =============================================================================
set -uo pipefail

KEEP="${KEEP_IMAGES:-3}"
DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

if ! [[ "$KEEP" =~ ^[1-9][0-9]*$ ]]; then
  echo "prune-images: KEEP_IMAGES debe ser un entero >= 1 (valor: '$KEEP')" >&2
  exit 0
fi

SERVICES=(api web icy-worker scripts)
TAB=$'\t'
removed=0
kept_in_use=0

for svc in "${SERVICES[@]}"; do
  repo="radio-gofestivals/${svc}"
  # "<fecha><TAB><tag>", solo tags tipo SHA, de más reciente a más antiguo; se descartan
  # los KEEP primeros y se devuelven el resto.
  mapfile -t old_tags < <(
    docker image ls "$repo" --format "{{.CreatedAt}}${TAB}{{.Tag}}" 2>/dev/null \
      | awk -F'\t' '$2 ~ /^[0-9a-f]{7,40}$/' \
      | sort -r \
      | awk -F'\t' -v keep="$KEEP" 'NR > keep { print $2 }'
  )
  for tag in "${old_tags[@]}"; do
    [[ -z "$tag" ]] && continue
    if (( DRY_RUN )); then
      echo "would remove ${repo}:${tag}"
      removed=$((removed + 1))
    elif docker rmi "${repo}:${tag}" >/dev/null 2>&1; then
      echo "removed ${repo}:${tag}"
      removed=$((removed + 1))
    else
      echo "kept (in use) ${repo}:${tag}"
      kept_in_use=$((kept_in_use + 1))
    fi
  done
done

verb="removed"
(( DRY_RUN )) && verb="would remove"
echo "prune-images: ${verb} ${removed} image tag(s), kept ${kept_in_use} in use (keep last ${KEEP} per service)"
exit 0
