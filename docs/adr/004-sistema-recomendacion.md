# ADR 004 · Recomendaciones: ítem-ítem precomputado + blend on-the-fly

**Fecha:** 2026-06-10 · **Estado:** aceptado · **Diseño completo:** [../recommendations-plan.md](../recommendations-plan.md)

## Contexto

La app captura señales de afinidad (plays diarios por identidad anónima o logueada,
favoritos, votos, tendencias, géneros jerárquicos con confidence, país/idioma) pero el
único descubrimiento es el módulo *featured* global y la búsqueda. Queremos recomendaciones
personalizadas que aumenten retención sin burbuja, en un único VPS CX22 compartido.

Dos restricciones de datos condicionan cualquier enfoque: no se captura duración de
escucha (los plays son eventos binarios deduplicados por día UTC) y la mayoría de
identidades son `client_id` anónimos e efímeros, así que la matriz usuario-ítem es
dispersísima. Un modelo de factorización (ALS) o secuencial (SASRec) no tiene hoy
densidad de datos que lo alimente, independientemente de su coste de cómputo.

## Decisión

Similitud **emisora-emisora precomputada cada noche** (top-20 por emisora: 0.50 coseno de
géneros con propagación jerárquica + 0.25 Jaccard de co-oyentes + 0.15 idioma + 0.10 país)
en una tabla `station_similarity`, y **blend lineal on-the-fly por identidad** en el request
(semillas con time-decay → candidatos → score → `apply_genre_cap` + 2 slots de exploración),
con cache Redis 600s. Cold start por locale del navegador. Eventos de impresión/click en
`rec_events` para evaluación (interleaving por defecto; A/B clásico está infrapotenciado
con la base actual). ALS pospuesto con gatillo explícito: >5k identidades con ≥5 emisoras
distintas en 90 días.

## Consecuencias

**Positivas:** cero infra nueva (reusa cron nocturno, admin jobs, Redis, `apply_genre_cap`,
índices de `station_plays`); coste por request <20 ms; explicable; degrada con gracia a
content-based donde el colaborativo no tiene datos; el coste escala con el catálogo
(estable), no con los usuarios; los componentes del score se guardan desglosados para
re-pesar sin recomputar.

**Negativas:** no capta gustos latentes cross-género (mitigación parcial: propagación
jerárquica + co-play) ni contexto temporal en el MVP; la calidad del colaborativo depende
de una base de oyentes aún pequeña; dos tablas y un cron más que mantener; las métricas
de éxito (CTR, play-through) requieren instrumentar `rec_events` desde el día uno, sin lo
cual el sistema vuela a ciegas.
