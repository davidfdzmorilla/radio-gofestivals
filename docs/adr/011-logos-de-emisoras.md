# ADR 011 · Logos reales de emisoras

## Contexto

Las portadas de emisora eran un recuadro de color con las iniciales. Radio-Browser trae un
`favicon` por emisora: en una muestra real de 300 emisoras de techno lo tenían el 78 %, casi todos
`https`, en formatos mezclados (png, jpg, ico, webp) y repartidos en 144 hosts distintos para 236
logos. Eso descarta cargarlos directamente desde el navegador: no se pueden listar los hosts en
`next/image`, la CSP solo permite imágenes propias (`img-src 'self'`) y el visitante quedaría expuesto
a hosts de terceros, imágenes rotas o enormes.

## Decisión

Un proxy con copia propia, en cuatro piezas:

1. `rb_sync` guarda la URL de origen en `stations.favicon_url` (solo `http(s)`, sin espacios ni
   caracteres no imprimibles, longitud acotada; si Radio-Browser deja de traerla se conserva la
   última válida, como `homepage_url`).
2. El comando `fetch-logos` (cron nocturno tras `rb_sync`) descarga, valida y **re-codifica** cada
   logo a dos WebP propios (112 y 256 px, aspecto conservado) guardados en `station_logos` (bytea,
   en Postgres). `stations.logo_hash` copia el hash para que los listados sepan si hay logo sin JOIN.
3. `GET /api/v1/stations/{slug}/logo?size=sm|lg&v=<hash>` sirve el WebP propio, solo de emisoras
   activas y no ocultas. Con `v` igual al hash actual, caché inmutable de un año; sin él, una hora.
   ETag distinto por tamaño y 304 con `If-None-Match`.
4. Frontend: `StationCover` muestra el logo sobre un recuadro claro (se ve cualquier logo, también los
   oscuros o transparentes) y, si no hay o no carga, el recuadro de color con iniciales de siempre.
   Se usa en tarjetas, ficha y reproductor. Es un `<img>` normal: ya es un WebP propio de 256 px.

Defensas, en capas: guard SSRF en cada petición y redirección (ADR 008); tope de 2 MB durante la
descarga (también por `Content-Length`); dimensiones comprobadas con la cabecera ANTES de decodificar
(máx. 25 MP, contra bombas de descompresión) y mínimo de 64 px; lista cerrada de formatos raster (no
SVG, que es XML); y, sobre todo, **nunca se sirve el archivo de origen**, solo nuestro re-encode.
Máximo 2 descargas simultáneas por host. User-Agent honesto e identificable (`radio.gofestivals/1.0`),
sin `Referer`: un host que nos rechaza se anota como fallo y se reintenta con backoff, no se evade.

Estados de `station_logos`: `ok`; `failed` (red, HTTP, página HTML en vez de imagen; backoff de
1/3/7/14/30 días); `rejected` (no es raster decodificable, demasiado pequeña o grande, URL interna;
no se reintenta hasta que cambie la URL). Refresco mensual. Un refresco fallido conserva el logo válido
que ya había; una URL nueva descarta el anterior.

## Consecuencias

- Medido de punta a punta contra hosts reales (115 emisoras activas y visibles de techno): **86 logos
  (75 %)**, 18 fallos (10 son 404, 2 son 403, 2 son 429, 3 páginas HTML, 1 error SSL) y 11 rechazos (8
  menores de 64 px). Tamaño medio de 9,9 KB por emisora (2,6 KB + 7,3 KB; máximo 21 KB), unos 13 MB
  para todo el catálogo, dentro de los backups diarios existentes.
- Positivas: portadas reconocibles; ningún host de tercero ve a nuestros visitantes; la CSP no cambia;
  los listados no generan 404 porque `logo_hash` dice si hay logo.
- Negativas: **son marcas y logos de terceros**. Se guardan copias reducidas, como hace cualquier
  directorio, pero conviene un "ocultar logo" por emisora en el admin y atender solicitudes de retirada.
- Negativas: cobertura limitada (~75 % de las que lo intentan) y una parte de los hosts son servicios de
  subida de imágenes (i.ibb.co, postimg.cc) con enlaces que caducan.
- Negativas: una petición de imagen por tarjeta visible (carga diferida, cacheada un año). Lee de
  Postgres; con la caché inmutable casi no se repite.
- Negativas: el recuadro claro destaca sobre el fondo oscuro y mezcla estilos con las portadas de
  iniciales de las emisoras sin logo.
- Pendiente: la página de favoritos (su payload no lleva `logo_hash`), las imágenes OG de emisora y el
  admin para ocultar un logo. Si un host bloquea de forma sistemática, se documenta, no se evade.
