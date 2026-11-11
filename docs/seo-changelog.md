# SEO changelog · radio.gofestivals

Registro fechado de los cambios que afectan a rastreo, indexación y medición.
Horas en UTC (las de `deploy_done` en `/var/log/radio/deploys.jsonl`).
Detalle técnico en `docs/adr/015-criterio-de-indexabilidad.md` y `docs/adr/014-eventos-personalizados-ga4.md`.

## 2026-11-09

### Despliegues (UTC)

| Hora | sha | Contenido |
|---|---|---|
| 09:08:22 | `ce428fd` | Criterio de indexabilidad, `robots` por página, 308 de rutas sin idioma |
| 09:13:07 | `9f4227d` | Sitemap índice + hijos; `/sitemap-v2.xml` → 301 |
| 09:35:16 | `df01c20` | Sitemaps sin `lastmod` (`updated_at` no era un cambio real) |
| 09:58:28 | `6a63422` | Migración 0027 (trigger de `updated_at`) y `/sitemap-index.xml`; ver nota |
| 10:13:18 | `81cc9ee` | Merge del trigger: `lastmod` con `LASTMOD_EPOCH` |
| 10:43:45 | `ced0d19` | Intros T4, regla de títulos, atribución de GA tras el banner (T5) |

**Nota sobre el despliegue de las 09:58.** Salió con el sha `6a63422`, de la rama
`feat/station-updated-at-trigger`, no con `main`: `deploy.sh` construye el árbol
de trabajo y se había dejado esa rama activa. La migración 0027 llegó a prod
unas horas antes de su merge a `main` (10:13). Estaba aprobada y con tests, y
`LASTMOD_EPOCH` (11:00) es posterior, así que no afecta a los datos. Medida:
dejar el árbol en `main` antes de cada deploy.

### Qué cambió

1. **Criterio de indexabilidad único** (`lib/indexability.ts`), usado por
   `<meta robots>` y por los sitemaps. **650 URLs por idioma** en lugar de 1.585
   (estaciones 402, géneros 33, países 36, país×género 155, trending 19,
   estáticas 5).
   - Género ≥ 8 estaciones; si no, `noindex, follow`.
   - País ≥ 5 indexable; 3–4 `noindex, follow`; < 3 → 404. Pasan a
     `noindex, follow`: AL, NO, NZ, SE, SI (4) e ID (3). `pl` y `us` siguen
     indexables.
   - País×género ≥ 5; si no, 404.
   - Estación: visible, con logo, país, género y calidad ≥ 50, o en la lista
     blanca (`radio-medved`, `studio-92-92-5-fm-lima`, `radio-onimai`,
     `hardbestfm`). La lista no anula `hidden`; en la práctica solo afecta a
     `hardbestfm`.
   - Festivales (ficha e índice), `/new` y `/search`: `noindex, follow`, sin
     canonical y fuera del sitemap.
2. **Sitemap índice + hijos**: `sitemap-static.xml` (48 URLs), `sitemap-genres.xml`
   (66), `sitemap-countries.xml` (382) y `sitemap-stations.xml` (804). El mismo
   índice se sirve en `/sitemap.xml` y `/sitemap-index.xml`; `/sitemap-v2.xml`
   devuelve 301 a `/sitemap.xml`. `robots.txt` tiene una única línea
   `Sitemap: https://radio.gofestivals.eu/sitemap-index.xml`, sin `Host:`.
   Sin `changefreq` ni `priority`.
3. **308 en rutas sin idioma**, en un salto y con `Cache-Control: private, no-store`.
   `/` sigue en 307 y negocia idioma. `x-default` de la portada es
   `https://radio.gofestivals.eu`; el resto usa `/en/...`.
4. **`stations.updated_at` solo avanza con cambios de contenido** (migración 0027):
   campos visibles de la estación (`IS DISTINCT FROM`) y altas/bajas de géneros
   (trigger en `station_genres`). `rb_sync.replace_rb_tag_links` toca solo la
   diferencia. No se rellena el pasado. El sitemap emite `lastmod` solo si es
   posterior a `LASTMOD_EPOCH = 2026-11-09T11:00:00Z`; sin `lastmod` en páginas
   estáticas ni en el índice. Hoy: 0 `lastmod`, porque ninguna estación ha
   cambiado desde la época.
5. **Intros con datos reales (T4)** en género, país y país×género (recuentos,
   países, subgéneros, nombres de estaciones), solo en la página 1 del listado.
6. **Regla de títulos**: si `título + " · radio.gofestivals"` supera 60
   caracteres, se quita el sufijo de marca; el contenido nunca se trunca. Corregida
   la marca duplicada en `/es/genres` y `/es/festivals`.
7. **Atribución de GA tras el banner (T5)**: la landing (utm, referrer) se guarda
   en memoria y, al aceptar, se envía como `page_view` antes del de la página
   actual. Verificado en DebugView en prod.

### Verificación

- `apps/web/scripts/seo-check.mjs` contra prod tras cada despliegue: "TODO OK".
- **Vigilante de `updated_at`** (API pública, 12:12 UTC, tras el health-check de
  las 12:00): 1.230 estaciones, todas con `updated_at` en `2026-11-09T06`; máximo
  `06:00:03Z`. El health-check de las 12:00 no movió ninguna fila, con el trigger
  nuevo ya activo desde las 09:58.

### Envíos manuales en Search Console (David, 9 nov)

- `/sitemap.xml`
- `/sitemap-index.xml`

Ambos figuran como "No se ha podido obtener". Se considera un estado provisional
de Search Console (el servidor responde 200 con el índice correcto); revisar el
10 nov.

### Verificación en prod de T4 + T5 (9 nov, ~14:20 UTC)

Sin despliegue nuevo: prod corre `ced0d19` (imágenes `web`, `api` e `icy-worker`
con tag `ced0d19`; rama `feat/seo-content-and-ga-attribution` ya fusionada).
`feat/genre-editorial-techno` sigue sin fusionar.

- `seo-check.mjs` contra prod: TODO OK.
- `/es|en/genres/techno`, `/es/countries/de`, `/es/countries/de/techno`: 200,
  intro con cifras reales en el HTML del servidor, `BreadcrumbList` e `ItemList`,
  canonical propio, sin `noindex`. Página 2 de los tres tipos: sin intro.
- T5 en navegador real (Playwright contra prod): el primer hit a GA es un
  `page_view` con `dl` = URL de entrada con utm y `dr` = referrer; `play_start`
  con `country=ro` en minúsculas.
- Las 20 URLs de la lista de indexación (6 géneros y 4 países, es/en): 200,
  indexables y en el sitemap.

## 2026-11-11

### Revisión de /en/genres/* tras avisos de Search Console

Search Console decía que `/en/genres/house` no estaba en ningún sitemap ni tenía
enlaces internos, y que `/en/genres/{electronic,dance,techno,ambient}` estaban
"rastreadas, sin indexar" mientras sus versiones `/es` sí estaban indexadas.

Comprobado en prod (sin cambios de código en producción, no hubo despliegue):

- `sitemap-genres.xml`: 66 URLs = 33 géneros × (es, en); ningún género con una sola
  versión. `/en/genres/house` está en el sitemap, con hreflang es/en/x-default.
- Enlaces internos: `/en`, `/en/genres` y las fichas de emisora en inglés enlazan a
  `/en/genres/house`; ninguna página `/en` enlaza a rutas `/es`.
- HTML del servidor de `/en/genres/{techno,electronic,house,dance,ambient}`:
  `html lang="en"`, canonical a su propia URL `/en`, hreflang `en`, `es` y
  `x-default` recíprocos con `/es`, título e intro en inglés, sin `noindex`.
- Causa del aviso: Search Console sí leyó `/sitemap-index.xml` el 9 nov
  ("Correcto", 1.300 URLs). El "sin sitemap ni enlaces" de `/en/genres/house` viene de
  que la inspección de URL muestra los datos de descubrimiento del último rastreo, y
  Google nunca había rastreado esa URL. "Rastreada, sin indexar" en URLs nuevas en
  inglés es el estado habitual hasta que Google las evalúa.

### Cambios

- Test `paridad de idiomas en los sitemaps` (`sitemap-indexability.test.ts`): falla si
  cualquier ruta aparece en un idioma y no en el otro, en cualquier hijo.
- `seo-check.mjs` comprueba esa paridad contra prod en los cuatro sitemaps.
- Intros: `stationNames` descarta nombres que no empiezan por letra o dígito
  (`#join...`, `@x`, `[HD]`...), con test. Entra en el próximo despliegue.
