# ADR 009 · Festivales de gofestivals vía su API HTTP pública

## Contexto

La radio promete "vínculo con festivales del ecosistema" pero no mostraba ninguno. El proyecto
hermano gofestivals (Node/Express + Postgres, ~250 festivales) ya tiene un plan de cross-links
(`RADIO-CROSSLINKS-PLAN.md` en su repo) cuya Fase D, la reciprocidad en la radio, nunca se hizo. Sus
fases A-C sí están: enlaces desde sus fichas y un endpoint público
`GET /api/festivals?genre=&country=&upcoming=true&limit=` con CORS abierto a esta radio.

En la config de la radio existe `gofestivals_db_url`, de un enfoque anterior de acceso directo a su
base de datos que nunca se usó. Comprobado el 2026-11-05: `upcoming=true` devuelve 100 festivales entre
2026-11-21 y 2027-08-27, y 15 de los 20 géneros de la radio tienen al menos uno (14 tienen 3 o más).

## Decisión

Consumir la **API HTTP pública**, no la base de datos. Módulo "Próximos festivales de {género}" en
`/genres/[slug]` (hasta 4 festivales, ordenados por fecha), solo en la primera página y sin filtro de
país. Se pide desde el servidor con `revalidate` de 1 h y un límite de 3 s; ante cualquier fallo (red,
HTTP, JSON inválido, ítems mal formados) devuelve lista vacía y el módulo no se pinta. Se vuelve a
filtrar el pasado y a ordenar en la radio, sin fiarse de la API. Los enlaces van a la ficha en
gofestivals (`.es` para el idioma `es`, `.eu` para el resto), sin `nofollow` (mismo propietario,
valor contextual), con el slug generado igual que su `generateSlug`. URL base configurable con
`GOFESTIVALS_API_URL` (opcional).

## Consecuencias

- Positivas: sin credenciales ni acoplamiento al esquema de su base de datos; su API ya está
  pensada para esto; el módulo no puede romper la página (fail-soft) ni retrasarla más de 3 s en
  una regeneración.
- Positivas: 15 de 20 géneros muestran el módulo; los 5 sin festivales (`makina`, `noise`,
  `old-school`, `schranz`, `uptempo`) no pintan nada.
- Negativas: **relevancia limitada**. Cada festival lista entre 10 y 30 géneros y el orden de esa
  lista cambia entre consultas, así que no se puede saber su género principal. "Ambient" incluirá
  festivales generalistas que lo listan entre muchos otros. Hoy solo se ordena por fecha.
- Negativas: el algoritmo del slug está duplicado (su `generateSlug`). Si cambia, los enlaces siguen
  dando 200 (su ficha acepta cualquier slug), pero un slug vacío redirige y pierde el idioma.
- Negativas: la API no pagina y se queda en 100 por llamada; suficiente para "próximos".
- Negativas: `country_code` está relleno en solo ~57 % de una muestra de 100 festivales (backfill de
  la Fase C incompleto), así que los hubs de país se dejan para después.
- Negativas: dependencia de un servicio propio pero externo; los datos pueden tardar hasta 1 h
  (caché del fetch) más 5 min (ISR de la página) en reflejar un cambio.
- Pendiente: medir clics (el plan de cross-links preveía una "surface" propia en `rec_events`),
  hubs de país, y retirar `gofestivals_db_url` de la config si se confirma que nada lo usa.
