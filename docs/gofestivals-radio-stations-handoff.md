# Handoff para el agente de gofestivals: emisoras en la ficha de festival

Sustituye el enlace "Escucha {género} en radio.gofestivals" por 4-6 emisoras reales de los estilos del festival.

## Contrato de la API de la radio (desplegada cuando se mergee `feat/stations-for-genres`)

`GET https://radio.gofestivals.eu/api/v1/stations/for-genres?genres=techno,house&limit=6`

- `genres`: CSV de slugs de la radio (minúsculas, `[a-z0-9-]`, máx. 30, 50 caracteres cada uno). Inválido → 422.
- `limit`: 1-12, por defecto 6.
- Respuesta: `{ items: [StationSummary], total, page, size, pages }`. Campos útiles de cada item:
  `slug, name, country_code, city, genres[], logo_hash, primary_stream.bitrate/codec`.
- Orden: nº de géneros pedidos que cubre la emisora (desc), luego tendencia y calidad.
- Géneros desconocidos para la radio no fallan: simplemente no aportan. Lista vacía = sin resultados.
- Caché de 5 min en la radio; límite 60 req/min por IP. Llamarla desde el servidor de Next con `revalidate`.
- URL de la ficha: `https://radio.gofestivals.eu/{locale}/stations/{slug}` (`locale` es/en; de/fr/pt/it → en).
- Logo: `https://radio.gofestivals.eu/api/v1/stations/{slug}/logo?size=lg&v={logo_hash}` si `logo_hash`; si no, iniciales o sin imagen.
  `size` admite `sm` o `lg`.

## Pasos

1. **Mapeo género→slug**: reutilizar `radioUtils.js` (whitelist + alias + heurística de padre).
   Devolver TODOS los slugs mapeables del festival, deduplicados (no solo el primero).
   Si no hay ninguno → fallback al enlace actual a `/trending`.
2. **Cliente**: función servidor `fetchRadioStationsForFestival(slugs, limit=6)` con
   `fetch(url, { next: { revalidate: 3600 }, signal: AbortSignal.timeout(1500) })`.
   Cualquier error/timeout/lista vacía → `null` (nunca rompe ni retrasa la ficha).
3. **Componente servidor** `RadioStations` (HTML renderizado en servidor, no `useEffect`: así Google ve los enlaces).
   Tarjetas: logo, nombre, país, bitrate, y los géneros en común con el festival (intersección de `item.genres` y los slugs del festival).
   Cada tarjeta enlaza a la ficha de la emisora en la radio (sin `nofollow`, mismo dueño). Título: "Emisoras para ir calentando" / equivalente i18n en los 6 idiomas.
   Texto honesto: "populares", no "más escuchadas".
4. **Fallback**: si `null`, renderizar el `RadioCrossLink` actual.
5. **Imágenes**: usar `<img>` con `loading="lazy"`, ancho/alto fijos, o añadir `radio.gofestivals.eu` a `remotePatterns` de next/image y a `img-src` de la CSP si la hay.
6. **Si la ficha es client component**: extraer el bloque a un server component y montarlo en la página servidor; si no es posible, hacer la petición en `generateMetadata`/page y pasar los datos como props.
7. **Tests**: mapeo con varios géneros y duplicados; cliente con respuesta OK, timeout, 422 y lista vacía (fallback); intersección de géneros.
8. **Verificar en prod**: ficha con géneros mapeables muestra tarjetas en el HTML (`curl | grep radio.gofestivals.eu/es/stations`), ficha sin géneros muestra el enlace antiguo, y con la radio caída la ficha responde igual de rápido.

## CORS
No hace falta si la llamada es desde servidor. Solo si se hiciera desde el navegador habría que añadir `https://gofestivals.eu` y `https://gofestivals.es` a `CORS_ALLOWED_ORIGINS` de la radio.
