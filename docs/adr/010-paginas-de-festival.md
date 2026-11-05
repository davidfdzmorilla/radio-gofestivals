# ADR 010 · Páginas de festival en la radio

## Contexto

El módulo "Próximos festivales" (ADR 009) enlazaba directamente a la ficha en gofestivals. Para que
tenga sentido como pieza de la radio, y no solo como un enlace saliente, cada festival necesita una
página propia con las emisoras que encajan con su sonido, enlazada internamente desde los géneros y
con su sitio en el sitemap. La API pública de gofestivals no expone artistas ni cartel, solo datos
del festival y una lista de 10-30 géneros sin orden.

## Decisión

- Rutas `/[locale]/festivals` (índice de próximos, agrupado por mes) y
  `/[locale]/festivals/[id]/[slug]`. Una sola URL por festival: sin slug, con slug equivocado o con
  ceros a la izquierda se redirige a la canónica. Un id no numérico es 404 sin llamar a la API (ella
  responde 500). Una edición ya celebrada se muestra con `noindex`.
- Los géneros del festival se traducen a los de la radio con un diccionario de alias y una heurística
  de género padre (adaptada de gofestivals), que **solo puede devolver slugs que la radio tenga**
  (20 raíces y 7 subgéneros) y prefiere el subgénero cuando existe. Las emisoras se piden por los 3
  géneros raíz principales (los subgéneros suman a su raíz), repartiendo 6 huecos en proporción a su
  peso, sin repetir emisoras.
- Las tarjetas del módulo de género enlazan a la ficha de la radio; esta enlaza a gofestivals con un
  botón destacado y a la web oficial con `nofollow` (solo URLs http/https: el valor viene de una base
  de datos ajena y acaba en un `href`).
- Imagen del festival con `next/image` y un `remotePatterns` restringido al bucket de gofestivals y a
  `/festivals/**`, servida desde `/_next/image` (la CSP `img-src 'self'` no cambia). Una función solo
  admite esa URL, porque `next/image` lanza en el render con hosts no configurados. Si no hay imagen o
  no carga, se pinta un recuadro de color con las iniciales.
- Sitemap: el índice y los festivales próximos, con hreflang. Sin JSON-LD `Event` (es el rich result
  de gofestivals y duplicarlo daría señales contradictorias); solo `BreadcrumbList`.
- `apiFetch` gana `baseUrl` y `timeoutMs` para hablar con gofestivals, y los tipos de festival viven en
  `lib/types.ts`, como pide el CLAUDE.md de `apps/web`. Los listados son fail-soft; el detalle
  propaga los fallos para no cachear un 404 falso.

## Consecuencias

- Positivas: ~100 páginas nuevas indexables con enlazado interno desde los géneros, y un camino de
  vuelta a gofestivals con contexto.
- Negativas: **las imágenes de gofestivals están caídas** (el bucket S3 responde `AllAccessDisabled`;
  su propio optimizador también da 403). Hasta que se recupere, todas las páginas muestran el
  recuadro de respaldo, y la ruta de imagen no se ha podido verificar de punta a punta.
- Negativas: con el `loading.tsx` raíz, un "no encontrado" y una redirección salen con código 200
  (con `noindex` y `meta refresh`), igual que el resto de la radio, no con 404/301.
- Negativas: la relevancia es aproximada: se elige por frecuencia de géneros, no por el género
  principal del festival, que la API no indica. Hay festivales generalistas en todos los géneros.
- Negativas: la descripción de la ficha (recortada a 400 caracteres) coincide con la de gofestivals;
  la meta description no, es propia.
- Negativas: el diccionario de géneros está duplicado respecto al de gofestivals y puede divergir.
- Pendiente: hubs de país (`country_code` en ~78 % de los próximos), medir clics y retirar
  `gofestivals_db_url`.
