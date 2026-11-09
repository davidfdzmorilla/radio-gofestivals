# ADR 015 · Criterio único de indexabilidad y redirects de idioma

## Contexto

Search Console (9 nov 2026, 90 días): 1.593 URLs indexadas y 5.369 sin indexar, 3.660 de ellas
"rastreadas, sin indexar" (el triple que a finales de septiembre). Casi todo son listados finos
(emisoras sueltas y combinaciones pequeñas). Las páginas que sí posicionan son las de país y
país×género. El sitemap listaba 1.585 URLs por idioma sin criterio común con el `robots` de cada
página.

## Decisión

`lib/indexability.ts` es la única fuente: lo usan el `<meta robots>` de cada página y los sitemaps.
Lo no indexable lleva `noindex, follow` (sigue existiendo y pasando autoridad), salvo los
listados bajo su puerta de existencia, que siguen siendo 404.

| Tipo | Indexable si | Si no |
|---|---|---|
| Género | ≥ 8 emisoras | `noindex, follow` |
| País | ≥ 5 | 3–4: `noindex, follow`; < 3: 404 |
| País × género | ≥ 5 | 404 |
| Emisora | visible, con logo, país, género y calidad ≥ 50, o en la allowlist de GSC | `noindex, follow`; si la ocultó el clasificador, `noindex, nofollow` |
| Festivales (ficha e índice), `/new`, `/search` | nunca | `noindex, follow`, sin canonical, fuera del sitemap |

La allowlist (radio-medved, studio-92-92-5-fm-lima, radio-onimai, hardbestfm) salta calidad y
logo, no la ocultación: tres de las cuatro están ocultas por el clasificador y siguen `noindex`.
Las rutas sin prefijo de idioma redirigen con **308** de un solo salto (antes 307), con
`Cache-Control: private, no-store` porque el idioma de destino depende de cookie y
`Accept-Language`.

## Consecuencias

- (+) Por idioma: de 1.585 a ~650 URLs en el sitemap (emisoras 1.226 → 402).
- (+) Robots y sitemap no pueden divergir; hay tests de ambos.
- (−) Menos URLs indexables no garantiza que Google indexe las que quedan: eso depende del contenido.
- (−) Los festivales dejan de indexarse en la radio (su ficha canónica está en gofestivals.eu).
- (−) 6 países (AL, NO, NZ, SE, SI, ID) pasan de indexables a `noindex, follow`.
- Umbrales y allowlist deben revisarse con datos de GSC cada pocos meses.

## Sitemaps (T2)

`/sitemap.xml` es un `sitemapindex` con `sitemap-static.xml`, `sitemap-genres.xml`,
`sitemap-countries.xml` (país y país×género) y `sitemap-stations.xml`. Cada hijo lleva solo URLs
indexables, `hreflang` es/en/x-default y `lastmod` real (la emisora más reciente que lista la
página); sin `changefreq` ni `priority`. `/sitemap-v2.xml` devuelve 301 al índice y `robots.txt`
declara una sola línea `Sitemap:` (sin `Host:`). La construcción se comparte entre los cuatro
hijos con una caché en memoria de 10 min, y cada respuesta lleva caché HTTP de 1 h.

Verificación en un entorno desplegado: `node apps/web/scripts/seo-check.mjs [BASE] [muestras]`
(sitemap válido y sin festivales, redirects 308/301, muestra de cada tipo con 200, sin noindex y
canonical propio, y controles `noindex` fuera del sitemap).

## `lastmod` y `stations.updated_at` (migración 0027)

El sitemap no emite `lastmod` porque `updated_at` valía "hoy" para todo el catálogo: el trigger
`BEFORE UPDATE` lo avanzaba en cualquier UPDATE (health-check, tendencias, `quality_score`...).
La migración 0027 lo restringe a cambios de contenido (slug, nombre, web, logos, país, ciudad,
idioma, geo, `hidden`, `status`, `class_state`) con `ROW(...) IS DISTINCT FROM ROW(...)`, y añade
un trigger en `station_genres` para altas, bajas y cambios de género. `rb_sync.replace_rb_tag_links`
pasó a tocar solo la diferencia (antes borraba y reinsertaba, y habría movido la fecha cada
noche). No se rellena el pasado: el sitemap solo emitirá `lastmod` para cambios posteriores a
la migración. `station_streams` queda fuera a propósito (su `status` cambia con el health-check).
