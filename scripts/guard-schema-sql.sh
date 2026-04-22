#!/usr/bin/env bash
# Bloquea commits que tocan infra/sql/schema.sql salvo que el mensaje
# incluya el tag explícito [schema-intended]. Ver CLAUDE.md §4 regla 3
# y ADR 001.

set -euo pipefail

commit_msg_file="${1:-}"
if [[ -z "$commit_msg_file" || ! -f "$commit_msg_file" ]]; then
  echo "guard-schema-sql: commit message file no disponible, saltando." >&2
  exit 0
fi

# Cambios en schema.sql staged para el commit actual
if ! git diff --cached --name-only | grep -qx 'infra/sql/schema.sql'; then
  exit 0
fi

if grep -q '\[schema-intended\]' "$commit_msg_file"; then
  echo "guard-schema-sql: OK (marcado como [schema-intended])." >&2
  exit 0
fi

cat >&2 <<'EOF'
ERROR · commit bloqueado por guard-schema-sql

Estás modificando infra/sql/schema.sql. Ese archivo es el snapshot inicial
cargado por la migración alembic 0001; editarlo retroactivamente crea
divergencia con DBs ya desplegadas (ver CLAUDE.md §4 y ADR 001).

Opciones:
  1. Cambio real de schema → crea una migración: alembic revision -m "..."
  2. Erratas que NO cambian DDL (comentario, typo en seed, formato) →
     añade el tag [schema-intended] al subject del commit.

EOF
exit 1
