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

## Addendum · Fase 2 (2026-11-06): segundo clasificador con la suscripción de Claude Code

La banda `review` (~290 emisoras visibles) la resuelve un modelo, sin revisión humana. Decisión de
David: **sin gasto de API, solo suscripción**. Se descartó la clave de API aunque la documentación
oficial la recomienda para pipelines que alimentan un producto: la autenticación de suscripción
está pensada para "ordinary use" y la doc no dice expresamente que un cron esté permitido ni
prohibido (consultar a Anthropic Sales si se quiere certeza). Es un riesgo de términos asumido.

- `infra/deploy/classify-llm.sh` (cron 05:10 UTC) exporta candidatas (`classify-stations
  review-export`), las pasa en lotes por `claude -p` y guarda los veredictos (`apply-llm`).
- Sin `--bare` (no lee la suscripción); directorio vacío; `--tools ""`; `--strict-mcp-config
  --disable-slash-commands` (de ~160.000 a ~5.000 tokens de contexto por llamada); salida
  restringida por `--json-schema`; se retiran `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` para
  que nunca facture por API.
- Veredicto `electronic`/`not_electronic` con confianza >= 70 => `accepted`/`rejected`; si no,
  `review`. `class_evidence` (huella de nombre+tags) evita volver a preguntar por lo ya juzgado;
  el recálculo de reglas no pisa un veredicto vigente. Las decisiones `manual` no se tocan.
- Al primer fallo (límite de uso, sesión caducada, JSON inválido) corta: guarda los lotes ya
  resueltos y sale con 3 para que `run-job.sh` avise por Telegram. Lo no resuelto queda para la
  siguiente ejecución.
- Límites conocidos: el comportamiento exacto de `claude -p` al alcanzar el límite de la
  suscripción no está documentado (se trata como fallo genérico); el modelo solo ve nombre,
  país y tags, así que unas ~55 % de las dudosas siguen en `review` (medido en una muestra de 55).
  La política para ese residuo se decide en la Fase 3.
- Alerting: cualquier fallo de `claude` avisa por Telegram con la causa (límite de uso, sesión
  caducada, timeout o extracto del error; la clasificación del texto es heurística porque los
  mensajes de `claude -p` no están documentados); hay aviso de recuperación y un latido que
  `watchdog.sh` vigila (36 h) para el caso de que el job deje de ejecutarse.

### Addendum · Fase 2b (2026-11-06): evidencia de la web y de los últimos temas

Medido sobre las 287 emisoras que las reglas dejan en `review`, comparando el modelo con solo
nombre y tags contra el modelo con además la web de la emisora (`<title>`, meta-descripción,
palabras clave) y sus últimos temas (`now_playing`): las dudosas bajan del 52 % (148) al 41 %
(117). 54 se resuelven con razón (p. ej. una web que se presenta como "Electronic Music" o como
prog rock) y 23 emisoras decididas con solo nombre y tags pasan a `review` porque la web las
contradice (`90s90s - TECHNO`, cuya web describe "de grunge a RnB"), así que el segundo pase
**sustituye** al primero, no lo completa. No hubo ni un vuelco aceptada <-> rechazada. El 41 %
restante son emisoras mixtas de verdad, no falta de datos.

- `review-export --with-evidence` descarga la web (guard SSRF, tope de bytes, 25 s por página;
  cualquier fallo se ignora) y añade los últimos temas.
- `EVIDENCE_VERSION` entra en la huella: los veredictos con menos evidencia quedan obsoletos y se
  reevalúan una vez.
- Cobertura medida: web utilizable en el 80 % de las dudosas, temas en el 33 %.

### Addendum · Fase 3a (2026-11-06): ocultar las rechazadas

`classify-stations enforce` oculta las `rejected` con el `hidden` existente, marcadas `hidden_by =
'classifier'` (migración 0026) para reponerlas si se reclasifican sin tocar nunca lo oculto por
otra vía. Defensas: antigüedad mínima del veredicto (24 h), curadas solo con veredicto del segundo
clasificador, tope por ejecución (5 % del catálogo visible, mín. 10; si se supera no se aplica nada
y se avisa) y reposición sin tope. Las páginas de una emisora oculta siguen accesibles por URL
(como ya ocurría con las ocultas por spam); queda como mejora devolver `noindex` en ellas.

La categoría "mixta" (las `review`: visibles pero fuera de géneros, tendencias, sitemap y
recomendaciones) es la Fase 3b: exige tocar varias consultas y se entrega aparte.
