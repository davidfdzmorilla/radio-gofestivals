# ADR 001 · schema.sql como migración alembic 0001

## Estado
Aceptado · 2026-04-21

## Contexto

El proyecto necesita a la vez un schema SQL legible y versionable para que
personas sin conocimiento profundo de alembic puedan entender la estructura
de DB, y un mecanismo de migraciones formal para cambios futuros que mantenga
la trazabilidad de versión en entornos desplegados.

`infra/sql/schema.sql` contiene la DDL inicial completa: 7 tablas de dominio
(`genres`, `stations`, `station_genres`, `now_playing`, `festival_stations`,
`admins`, `curation_log`), 3 extensiones (`postgis`, `uuid-ossp`, `pg_trgm`),
3 tipos enum, índices incluyendo GIN trigram y GiST geography, triggers de
`updated_at` y el seed de la taxonomía de géneros base. Son ~230 líneas muy
densas pero directas de leer.

`docker-compose.yml` monta ese archivo en `/docker-entrypoint-initdb.d/` para
que una DB fresca quede operativa sin pasos extra. Paralelamente, alembic
necesita una migración inicial (revisión 0001) para empezar a trackear
versión y poder crear migraciones incrementales a partir de ahí.

## Decisión

La migración `0001_initial_schema.py` **carga y ejecuta `infra/sql/schema.sql`
como SQL crudo** en lugar de traducir las ~230 líneas a llamadas
`op.create_table(...)` / `op.create_index(...)` / `op.execute("CREATE TYPE ...")`.

La migración es **idempotente**: un guard previo
(`SELECT to_regclass('public.stations')`) detecta si el schema ya existe
— caso típico cuando `docker-entrypoint-initdb.d` ha corrido antes — y
en ese caso solo registra la versión en `alembic_version` sin reejecutar
el DDL. Esto permite que el flujo documentado en CLAUDE.md §5 funcione
sin fricción:

```
docker compose up -d postgres     # initdb.d carga schema.sql
uv run alembic upgrade head       # migración 0001 se marca como aplicada
```

A partir de **0002**, las migraciones siguen el flujo estándar
(`alembic revision --autogenerate`) contra `Base.metadata` de los modelos
SQLAlchemy.

## Consecuencias

### Positivas

- **Una única fuente de verdad** para el schema inicial: el SQL está en un
  solo sitio, mantenible con las herramientas que todo el equipo ya conoce
  (`psql`, editor con syntax highlight de SQL, revisión en PR legible).
- **schema.sql sigue siendo útil** para nuevos miembros del equipo, admins
  de DB y scripts de debugging sin que tengan que entender el DSL de
  alembic ni ejecutar Python para ver la estructura.
- **Bootstrap docker y alembic conviven** sin duplicación ni divergencia:
  los dos caminos de creación de schema apuntan al mismo archivo.

### Negativas / riesgos

- **Los modelos SQLAlchemy de `app/models/` son una reimplementación manual
  de `schema.sql`**. Cualquier divergencia entre ambos (p.ej. tipos
  incorrectos, nullable distinto, CHECK constraints faltantes) es silenciosa
  hasta que un test de integración falla. Mitigación: la suite
  `tests/integration/` ejerce cada modelo contra la DB real; cualquier
  drift de tipo aflora ahí.
- **`alembic downgrade 0001` no revierte limpio**. El downgrade actual hace
  `DROP TABLE ... CASCADE` explícito pero no desinstala las extensiones
  ni rehace el estado "pre-0001" de forma prístina. Aceptable: revertir la
  migración inicial no es un caso de uso real en producción, solo en tests
  de regresión locales.
- **Futuros cambios de schema DEBEN ir por migraciones 0002+, nunca
  editando `schema.sql` retroactivamente**. Si alguien modifica
  `schema.sql` pensando que es la fuente viva, crea divergencia con el
  estado real de las DBs ya desplegadas (que fueron a 0001 y están
  esperando 0002). Este riesgo se mitiga con la nota en la cabecera del
  propio archivo y con revisión de PR.
