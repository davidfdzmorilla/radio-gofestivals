# ADR 012 · Clasificación automática "¿es electrónica?" del catálogo

## Contexto

Una emisora entra al catálogo al aparecer en la búsqueda de Radio-Browser por uno de 15 tags
(`techno`, `house`, `minimal`, `progressive`, `ambient`, `electronic`…). Varios son ambiguos
(`progressive` trae rock progresivo; `house`, radios locales; `ambient`, new age) y el `upsert`
ocurre antes de comprobar si la emisora tiene algún género nuestro. Medido en prod el
2026-11-06: 228 de 1.665 emisoras visibles (14 %) no tienen ningún género y solo 2 están curadas;
entre ellas hay prog rock, radio hablada y pop, pero también electrónica real que el mapeador de
tags no reconoce (`Radio Techno Chile`, `UKG Radio`).

Además no se guardaba la evidencia (los tags crudos), así que no se podía reclasificar sin volver a
Radio-Browser, y `curated` es la única señal editorial, hecha a mano.

El requisito es que el flujo sea **automático**, sin revisión humana en el camino.

## Decisión

Clasificar cada emisora con una puntuación 0-100 y tres estados (`accepted`, `review`,
`rejected`), en fases:

1. **Fase 1 (esta)**: guardar `rb_tags` y las columnas de veredicto; clasificador de reglas puro
   (`station_classifier.py`) en **modo sombra**: se registra el veredicto, nada oculta. Comando
   `classify-stations` (`backfill-tags`, `run`).
2. Fase 2: umbrales calibrados y un segundo clasificador (modelo de Claude) para la banda `review`.
3. Fase 3: aplicarlo (nuevas emisoras no visibles hasta `accepted`), con topes y alertas.

Reglas de diseño: lo ambiguo solo suma junto a un tag electrónico claro; el nombre solo desempata
(no acepta ni rechaza); un veredicto `manual` o una emisora `curated` no se pisan; ocultar no
borra; un cambio masivo en un ciclo no se aplica y avisa.

## Consecuencias

- Positivas: evidencia persistida y reclasificable; medición sobre el catálogo real antes de actuar;
  sin riesgo en prod (las columnas no las lee nada todavía).
- Negativas: las reglas por tags no ven el contenido real de la emisora (una radio mixta etiquetada
  "house" y "pop" queda en `review`); el criterio de frontera (ambient, chill-out, dance-pop) es una
  decisión editorial pendiente, ahora fijada por constantes en `station_classifier.py`; sin
  revisión humana, la calidad depende de calibrar bien los umbrales y de la auditoría automática
  de las fases 2-3.
- Medido offline sobre 1.430 emisoras devueltas por Radio-Browser para los 15 tags: 996 aceptadas,
  238 en revisión, 196 rechazadas.
