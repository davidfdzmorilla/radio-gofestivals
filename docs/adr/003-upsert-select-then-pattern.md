# ADR 003 · SELECT-then-INSERT-or-UPDATE en rb_sync (vs ON CONFLICT)

## Estado
Aceptado · 2026-04-21

## Contexto

La sincronización con Radio-Browser (`packages/scripts/scripts/rb_sync.py`)
debe actualizar ~1000-5000 estaciones en cada ejecución diaria. El schema
tiene tres tipos de columnas en `stations` con semántica muy distinta:

- **Columnas técnicas** que Radio-Browser controla:
  `name`, `stream_url`, `codec`, `bitrate`, `language`, `country_code`,
  `city`, `geo`, `last_sync_at`. Deben reflejar el estado upstream en cada sync.
- **Columnas editoriales** controladas por humanos vía la UI de curación:
  `curated`, `quality_score`, `status`, `failed_checks`. No deben tocarse
  nunca durante un sync; cambiarlas pisaría trabajo manual.
- **Columnas de identidad**: `id`, `slug`, `rb_uuid`, `source`, `created_at`.
  Inmutables o solo se tocan en la creación inicial.

La primera implementación candidata era el patrón idiomático de
SQLAlchemy/PostgreSQL `INSERT ... ON CONFLICT (rb_uuid) DO UPDATE SET ...`.
Elegante y atómico, pero un error tipográfico incluyendo `curated` o `status`
en el `SET` dispararía una pérdida silenciosa de estado editorial en TODAS
las estaciones afectadas, sin señal visible hasta que el curador lo note.

## Decisión

Usar el patrón **SELECT-then-INSERT-or-UPDATE**:

1. `SELECT id, slug, status FROM stations WHERE rb_uuid = :rb`
2. Si no existe → `INSERT` con los campos técnicos y defaults para
   `curated=false`, `quality_score=50`, `status='pending'`.
3. Si existe → `UPDATE stations SET <solo columnas técnicas>, last_sync_at = now()
   WHERE id = :id`. El `SET` **nunca** menciona columnas editoriales.

El patrón es más verboso y requiere una query extra por estación, pero hace
que la restricción esté codificada en la forma del código: para pisar un
campo editorial hay que añadirlo explícitamente al `UPDATE SET`. Un
descuido en una futura PR es visible en review ("¿por qué este UPDATE
toca `curated`?").

Para los vínculos N:M `station_genres` el patrón análogo es:
`DELETE ... WHERE source = 'rb_tag'` seguido de `INSERT` con los nuevos
matches — se preservan las entradas con `source = 'manual'`.

## Consecuencias

### Positivas

- **Imposible de romper por descuido**: los campos editoriales no aparecen
  en el `UPDATE SET`, así que no se pueden pisar sin una modificación
  explícita y revisable del SQL.
- **Test de regresión simple y barato**:
  `test_preserves_curated_flag_and_status` y `test_preserves_broken_status`
  lo verifican con <30 líneas; si alguien rompe la invariante, el test
  se pone rojo inmediatamente.
- **Legibilidad**: el flujo "busco, decido crear o actualizar" es más
  fácil de leer que un `ON CONFLICT DO UPDATE` con un `SET` de 10 columnas.

### Negativas / riesgos

- **2 queries por estación en lugar de 1**. A volúmenes actuales
  (~1000 estaciones, sync nocturno, ~10-20 segundos en total) es
  irrelevante. Si el catálogo crece a 100k, revisar.
- **Race condition teórica**: si dos procesos corren `rb_sync run` en
  paralelo contra la misma DB, el `SELECT` del segundo puede ver un
  estado "previo a INSERT" y reintentar un INSERT que violará la
  unique constraint de `rb_uuid`. No aplica al escenario actual (cron
  nocturno, 1 proceso). Si algún día se paraleliza el sync, las
  opciones son: (a) wrap en `SELECT ... FOR UPDATE`, o (b) capturar la
  excepción de unique violation y degradar a UPDATE. Ambas son fáciles
  de añadir cuando se necesiten; no merece complejizar ahora.
- **Divergencia con el idiom "Upsert" del PDF técnico §08**. El PDF
  muestra `INSERT ... ON CONFLICT DO UPDATE` como ejemplo. La decisión
  aquí la contradice deliberadamente por las razones de arriba. El PDF
  describe el patrón mecánico; este ADR captura por qué optamos por
  otra forma.
