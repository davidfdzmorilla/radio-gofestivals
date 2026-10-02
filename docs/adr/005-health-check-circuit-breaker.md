# ADR 005 · Circuit breaker en el health-check de streams

## Contexto

El health-check (`rb_sync health-check`, cron cada 6 h) incrementa `failed_checks`
por cada stream que falla y lo marca `broken` al llegar a `HEALTH_MAX_FAILURES`.
Un stream "falla" también cuando el problema es nuestra propia red (timeout, DNS,
connect error), no la emisora.

Entre el 2026-10-01 12:00 y el 2026-10-02 06:41 UTC, cuatro pasadas consecutivas
dieron timeout en ~98% de los streams (la red de salida del contenedor estaba
caída durante cada run). Resultado: 1814 streams marcados `broken` y el catálogo
público pasó de ~1500 a 71 estaciones activas, aunque las emisoras seguían vivas.
Se recuperó lanzando de nuevo el health-check, que repone `active` al primer éxito.

La línea base sana es ~3% de fallos de transporte (timeouts, DNS) sobre ~2300 streams.

## Decisión

El health-check hace primero todos los probes sin escribir en la BD. Si hay al menos
50 streams y más del 50% fallan a nivel de transporte (`alive=False` y
`status_code=None`), aborta: no actualiza `failed_checks`, `status` ni la cascada
a estaciones, registra `health_check_aborted` con nivel error y devuelve
`aborted=1` en las stats.

## Consecuencias

- Positivas: una caída de red local ya no degrada el catálogo; el error queda en el log.
- Positivas: los probes se separan de las escrituras (más fácil de testear).
- Negativas: durante un abort real de muchas emisoras (p. ej. caída de un CDN grande
  con >50% del catálogo) tampoco se marcan caídas hasta que se resuelva; se acepta.
- Negativas: los resultados de todos los probes se mantienen en memoria hasta el final
  (~2000 objetos pequeños; irrelevante a esta escala).
- Pendiente: nada alerta aún de `health_check_aborted`; hoy solo se ve en el log.
