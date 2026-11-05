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

## Addendum · fuente alternativa: el icono de la web de la emisora (2026-11-05)

**Contexto.** Con solo el favicon de Radio-Browser, el backfill dejó logo en 715 de 1.651 emisoras
activas (43 %): 963 tenían favicon (58 %) y de esas se aprovechó el 74 %. De las 936 sin logo, 907
(96 %) tienen `homepage_url`.

**Medición previa** sobre una muestra real de 120 de esas webs (mismo guard y mismo procesado):
80 (66 %) dieron un icono utilizable: 58 por `apple-touch-icon`, 17 por `og:image` y 5 por
`<link rel=icon>`. Se montó una hoja de contactos con los 80 y se miró a ojo: el `apple-touch-icon`
da logos reales y reconocibles; el `og:image` da fotos y banners, no logos; y salían falsos
positivos evidentes (el logo de Wix en 3 webs, el de la plataforma `laut.fm`, un icono blanco sobre
el recuadro blanco).

**Decisión.** Escalera de fuentes en `fetch-logos`: 1) favicon de Radio-Browser; 2) si no sirve, el
icono de marca de la web (`homepage_url`): se lee la web una vez (300 KB máx., con el guard SSRF y el
User-Agent honesto) y se prueban, por este orden, `apple-touch-icon` (mayor lado declarado primero),
`<link rel=icon>` (se omiten los declarados de menos de 64 px) y `/apple-touch-icon.png`. **No se usa
`og:image`** (calidad), ni SVG, ni `mask-icon`. Se descartan las webs de redes sociales, plataformas de
radio y constructores genéricos (lista por dominio, no por subcadena: `xlukradio.com` no es
`radio.co`), y todo icono que se perdería sobre el recuadro claro (menos de un 2 % de píxeles se
distingue de él: blanco sobre transparente, fondo casi blanco…); esta última comprobación también
afecta a los favicons.

Migración 0022: `station_logos` guarda `favicon_seen` y `homepage_seen` (las URLs que había al
intentarlo; si cambian, la emisora vuelve a la cola) y `source_kind` (`favicon`/`homepage`). Las
filas existentes con logo no se tocan; las `failed` y `rejected` quedan con `homepage_seen` vacío y
entran solas a probar la web. Una web que responde pero no tiene icono es un fallo reintentable
(backoff hasta 30 días, puede añadirlo); una web social, de plataforma o que apunta a una dirección
interna es un rechazo definitivo hasta que cambie la URL.

**Resultado medido** (386 emisoras reales de Radio-Browser: techno, house, trance, ambient): cobertura
del **52 % con solo favicon al 70 % con la escalera** (+72 logos desde la web, 48 s). Revisados a ojo,
los 72 son logos de marca reconocibles; no aparece ningún logo de plataforma.


**Control de calidad tras el backfill (2026-11-05).** Con la cobertura ya en 72 % (1.199 de 1.651), se
agruparon los logos por hash para buscar imágenes repetidas. De los 114 hashes compartidos casi todos
eran marcas legítimas con muchos canales (Radio Record 23, rautemusik 16, DFM 16, NTS 9, SomaFM 8…).
Pero uno, una nota musical azul, estaba en 8 emisoras de hosts sin relación (`r.bgp.rodeo`,
`asurahosting.com`, `costa-server.info.pl`): el icono por defecto de un software de gestión de radio.
Regla añadida, y aplicada en cada pasada de `fetch-logos` (`purge_unwanted_logos`): **una misma imagen
en 3 o más sitios distintos** (dominio registrable aproximado, para que `a.marca.fm` y `b.marca.fm`
cuenten como uno) se considera icono genérico y se rechaza. La misma pasada vuelve retroactiva la
lista de dominios denegados: un logo de la web cuyo dominio se añade después a la lista se retira. Los
logos que vienen del favicon de Radio-Browser no se tocan. Límite: el umbral es una heurística; una
marca con 3 dominios distintos y el mismo logo, o dos sitios con el mismo icono genérico, no se
distinguen de forma fiable.

**Consecuencias.**
- Positivas: unos +440 logos esperados en el catálogo completo (de ~43 % a ~70 %) con calidad de marca.
- Negativas: una petición más por emisora sin logo (la web) y otra por icono probado, como mucho una
  vez al mes por emisora tras el primer intento. No se consulta `robots.txt`: se lee una página
  pública con un User-Agent identificable, y un host que responde 403/429 se respeta (fallo con
  backoff), no se evade.
- Negativas: falsos positivos que no se pueden detectar de forma fiable, como una web que usa el icono
  por defecto de su framework (visto: el logo de React en una emisora). Varias emisoras de una misma
  marca comparten logo, lo que es correcto.
- Negativas: la lista de dominios denegados es manual; hay que ampliarla si aparecen plataformas nuevas.
- Pendiente: `og:image` descartado a propósito; revisar si en el catálogo completo compensa una regla
  más fina (por ejemplo, solo si es casi cuadrada).
