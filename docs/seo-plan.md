# Estrategia SEO orgánico · radio.gofestivals.eu

> Plan estratégico de SEO técnico, programático y de crecimiento.
> Elaborado 2026-06-10 sobre auditoría del código y muestreo del catálogo real.
> Roadmap vivo: actualizar al cerrar cada fase.

---

## 0 · Punto de partida (auditoría)

**Lo que ya existe y está bien**: metadata por página con canonical + hreflang
(`lib/seo.ts` → `buildAlternates`, en/es + x-default), JSON-LD (WebSite +
Organization en layout; BreadcrumbList + CollectionPage/ItemList en géneros;
BreadcrumbList + RadioStation con PostalAddress/inLanguage en emisoras),
sitemaps duales (`app/sitemap.ts` nativo + `sitemap-v2.xml` force-dynamic para
GSC) con hreflang en XML, `robots.ts`, ISR en todo (home/géneros 300s,
emisoras 60s), `generateStaticParams` para géneros raíz.

**Lo que falta** (= el trabajo): solo hay 3 tipos de página indexables (home,
géneros, emisoras). No existen páginas de país, ciudad, idioma, rankings,
nuevas ni búsqueda — ni los endpoints de facetas del API que las harían
posibles. Páginas auth/cliente sin `robots: noindex` (solo robots.txt, que no
impide indexación). Sin imágenes OG. Fuentes display vía CDN de Fontshare.

**Datos reales del catálogo** (muestreo 2026-06-10): **1.259 emisoras
activas**; ~44+ países en muestra de 300 (top DE 75 · US 28 · GB 27 · RU 23 ·
FR 15); ciudad presente solo en ~57% y muy fragmentada (87 ciudades distintas
en 300 emisoras, mediana 1-2 emisoras/ciudad); `language` es texto libre CSV.

**Bug encontrado en la auditoría**: `lib/sitemap-data.ts` emite
`x-default=es` mientras `lib/seo.ts` emite `x-default=en` — señales hreflang
contradictorias a Google. Fix en fase 0-30.

### Nota de honestidad sobre la escala

No hay "millones de páginas" ni conviene perseguirlas. Con 1.259 emisoras ×2
locales + hubs programáticos con umbrales de calidad, la superficie indexable
realista es de **~3.500–5.000 URLs hoy**, y ~15.000–40.000 si el catálogo
crece a 5–10k emisoras vía `rb_sync` (la cola de Radio-Browser pierde calidad
rápido). Eso es *bueno*: los directorios que indexan combinatoria thin
(ciudad×género×idioma sin emisoras) son los que Google desindexa desde
Helpful Content. Esta estrategia usa **gates de contenido desde el día 1** y
una arquitectura que escala cuando el catálogo lo justifique.

---

## 1 · Arquitectura SEO

### 1.1 Esquema de URLs

Mantener subdirectorios de locale + **slugs en inglés no localizados**
(`/es/genres/techno`, no `/es/generos/techno`): es el patrón existente,
localizar slugs exigiría tablas de mapeo y redirecciones (coste alto,
beneficio marginal — la keyword pesa en title/H1/contenido, que sí se
localizan), y `buildAlternates` asume el mismo `pathWithoutLocale` para todos
los locales.

**Países por código ISO** (`/countries/de`): `country_code` es CHAR(2) en el
modelo — ruta 100% data-driven sin tabla de mapeo, y
`Intl.DisplayNames(locale, {type:'region'}).of('DE')` da el nombre localizado
gratis para title/H1/breadcrumb.

```
/{locale}/                              home (hub raíz)
/{locale}/genres                        índice de géneros (existe)
/{locale}/genres/{slug}                 hub de género (existe) — hub PRIMARIO
/{locale}/countries                     índice de países (NUEVO)
/{locale}/countries/{iso2}              hub de país (NUEVO)
/{locale}/countries/{iso2}/{genre}      combo país×género, gated (NUEVO, fase 2)
/{locale}/languages                     índice de idiomas (NUEVO, fase 3)
/{locale}/languages/{lang}              hub de idioma, gated (NUEVO, fase 3)
/{locale}/trending                      ranking global por click_trend (NUEVO)
/{locale}/trending/{genre}              ranking por género, gated (NUEVO)
/{locale}/new                           emisoras nuevas (NUEVO)
/{locale}/search                        búsqueda — target del SearchAction (NUEVO)
/{locale}/stations/{slug}               ficha de emisora (existe) — hoja
```

### 1.2 Jerarquía y profundidad

**Toda emisora a ≤3 clics de la home**: home → género (o país) → emisora.
Los combos quedan a profundidad 2 y enlazan emisoras a profundidad 3.

```
                        ┌─────────── HOME ───────────┐
                        │  top géneros + top países   │
                        │   + trending + nuevas       │
                        └──┬────────┬────────┬───────┬┘
              ┌────────────┘        │        │       └──────────┐
        /genres (20)          /countries (~60)   /trending   /new
              │                     │                │
        /genres/techno   ←──→  /countries/de         │
              │    ╲               ╱   │             │
              │     /countries/de/techno             │
              │            │          │              │
              └──────► /stations/{slug} ◄────────────┘
                        (1.259 × 2 locales)
                     │ módulo "similares" (lateral, YA existe)
                     │ links ascendentes: género, país, idioma
```

### 1.3 Hub topical primario: el género

En un sitio de radio *electrónica* el género es la entidad con intención de
búsqueda real ("techno radio online"); el país es secundario y el idioma
terciario. Los hubs de género reciben la mayor inversión de contenido (intro
editorial, FAQs, ranking propio, link a su combo país más fuerte) y la home
enlaza los ~20 nodos de la taxonomía de forma permanente.

### 1.4 Reglas de enlazado interno

1. **Ficha de emisora enlaza hacia arriba**: su(s) género(s), su país, su
   idioma cuando exista el hub. Hoy son texto plano — convertir en `<Link>`.
2. **Lateral**: módulo de similares ya existente — debe renderizarse
   server-side (HTML en el ISR) para contar como enlace.
3. **Hub de género** enlaza: top-N emisoras (ItemList visible), subgéneros, y
   los 5-8 combos país×género con más emisoras ("Techno en Alemania (142)").
4. **Hub de país** enlaza: top emisoras + géneros con ≥5 emisoras del país →
   **cada combo recibe ≥2 enlaces internos** (desde género y desde país).
5. **Breadcrumbs visibles + BreadcrumbList** en toda página ≥profundidad 1,
   por la ruta del género primario (no del país).
6. **Anchors descriptivos y localizados** ("radios de techno en Alemania"),
   nunca "ver más".
7. **Cero huérfanas**: todo lo que entra al sitemap tiene ≥1 enlace interno.

---

## 2 · SEO programático (con gates anti-thin)

**Prerequisito backend** (bloquea toda la capa): endpoints de facetas en
FastAPI (`app/repos/stations.py` + `app/api/v1/stations.py`):

```
GET /api/v1/stations/facets/countries            → [{code:"DE", station_count:180}, …]
GET /api/v1/stations/facets/countries?genre=techno  → mismo shape, filtrado (gating)
GET /api/v1/stations/facets/languages            → requiere normalizar el CSV (fase 3)
GET /api/v1/stations/trending?genre=&limit=50    → por click_trend desc
GET /api/v1/stations/new?limit=50                → por created_at desc
```

### Matriz de viabilidad

| Página | Gate de publicación | Volumen ×2 locales | Fase |
|---|---|---|---|
| `/countries/{iso2}` | ≥3 emisoras activas | ~110 | 1 |
| `/countries/{iso2}/{genre}` | **≥5 emisoras en el combo** | ~300-600 | 2 |
| `/trending` + `/trending/{genre}` | género con ≥10 emisoras con señal | ~40 | 1-2 |
| `/new` | — | 2 | 1 |
| `/languages/{lang}` | ≥10 emisoras + vocabulario normalizado | ~25 | 3 |
| Ciudades | **NO todavía** — ~57% de cobertura y mediana 1-2 emisoras/ciudad. Plegar como sección dentro de la página de país. Revisitar cuando Berlín/Londres/Moscú superen ~10 emisoras. | — | — |

**Comportamiento del gate**: combo bajo el umbral → no se genera, no entra al
sitemap, no recibe enlaces. Página publicada que cae bajo el umbral → 410 o
301 al hub padre. El gate se evalúa en `generateStaticParams` Y en el sitemap
**con la misma fuente** (endpoint de facetas) para que nunca diverjan.

### Qué hace no-thin cada plantilla

Contador real + ItemList top-10 por trending + **intro de 80-150 palabras
generada desde datos** con plantilla ICU parametrizada ("Alemania aporta {N}
emisoras; domina el {género_top} con {n} radios, seguido de {género_2}…" —
los datos varían por página, no es boilerplate) + sección de combos/géneros
enlazados + 2-4 FAQs data-driven ("¿Cuál es la radio de techno alemana más
escuchada?" → respuesta desde click_trend, se actualiza sola).

**Riesgo de duplicado principal**: los combos compiten con el filtro actual
`?country=` de las páginas de género. Resolución: canonical del filtro al
combo cuando este exista y pase el gate; migrar el filtro del sidebar a
navegación a la ruta dedicada.

---

## 3 · Clusters de keywords

**Realismo competitivo**: "escuchar radio online" / "internet radio"
pertenecen a TuneIn, mytuner, radio.net, Streema (DA 70-90) — no se compite
ahí. El espacio ganable: **(a)** nicho electrónico genérico, **(b)** longtail
combinatoria, **(c)** marcas de emisoras pequeñas (las netlabel-radios apenas
tienen presencia propia → la ficha puede rankear para su marca).

| # | Cluster | Ejemplos | Dificultad | Página destino | Prioridad |
|---|---|---|---|---|---|
| 1 | Género + radio (EN) | "techno radio", "house music radio online", "drum and bass radio" | Media | `/genres/{slug}` | **P1** |
| 2 | Género + radio (ES) | "radio techno online", "radio electrónica en directo", "emisoras de música electrónica" | Media-baja | `/genres/{slug}`, home | **P1** |
| 3 | Género × país | "techno radio germany", "french house radio", "radio techno alemana" | **Baja** (alto agregado) | `/countries/{iso2}/{genre}` | **P1** |
| 4 | Marca de emisora | "{nombre} online", "escuchar {nombre}" (~1.259 fichas) | Muy baja | `/stations/{slug}` — mejorar title: `{Nombre} — escuchar en directo \| {género}, {país}` | **P1** |
| 5 | Mejores/rankings | "best techno radio stations 2026", "mejores radios de electrónica" | Media | `/trending`(+género) | P2 |
| 6 | País genérico | "radio electrónica alemania", "electronic radio stations uk" | Baja | `/countries/{iso2}` | P2 |
| 7 | Informacional | "qué es el techno melódico", "diferencia house y techno" | Media | guías en hubs (§8) | P2-P3 |
| 8 | Idioma | "radio electrónica en español" | Baja | `/languages/{lang}` | P3 |
| 9 | Festival-adjacent | "música de {festival}", "radio estilo awakenings" | Baja | contenido cruzado gofestivals | P3 |

Motor realista de las primeras 10k visitas/mes orgánicas: el agregado de los
clusters 3+4 (cientos de keywords de 10-100 búsquedas/mes sin competencia
seria).

---

## 4 · Schema.org (sobre la base existente)

**(a) Fix inmediato — BreadcrumbList de emisora**: el último `ListItem`
carece de `item` URL; añadir la URL canónica de la ficha.

**(b) SearchAction en WebSite** (solo tras construir `/search` — no declarar
un target inexistente):

```json
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "url": "https://radio.gofestivals.eu",
  "potentialAction": {
    "@type": "SearchAction",
    "target": { "@type": "EntryPoint",
      "urlTemplate": "https://radio.gofestivals.eu/es/search?q={search_term_string}" },
    "query-input": "required name=search_term_string"
  }
}
```

*Impacto honesto*: el sitelinks searchbox fue deprecado visualmente en 2024;
sigue siendo señal de entendimiento del sitio, coste ~0.

**(c) BroadcastService + ListenAction en fichas** — complemento del
`RadioStation` existente, expone el stream como entidad:

```json
{
  "@context": "https://schema.org",
  "@type": "BroadcastService",
  "name": "HardTechno Radio Berlin",
  "url": "https://radio.gofestivals.eu/es/stations/hardtechno-radio-berlin",
  "provider": { "@id": "https://radio.gofestivals.eu/#org" },
  "broadcastAffiliateOf": { "@type": "RadioStation",
    "@id": "https://radio.gofestivals.eu/es/stations/hardtechno-radio-berlin#station" },
  "inLanguage": "de",
  "genre": ["Techno", "Hard Techno"],
  "potentialAction": {
    "@type": "ListenAction",
    "target": { "@type": "EntryPoint",
      "urlTemplate": "https://radio.gofestivals.eu/es/stations/hardtechno-radio-berlin",
      "actionPlatform": ["https://schema.org/DesktopWebPlatform",
                         "https://schema.org/MobileWebPlatform"] }
  }
}
```

*Impacto honesto*: no hay rich result de radio hoy; apuesta a entendimiento
de entidad. Coste bajo.

**(d) ItemList en `/trending`** — reutilizar el patrón de las páginas de
género con posición = ranking real:

```json
{
  "@context": "https://schema.org",
  "@type": "ItemList",
  "name": "Radios de techno más escuchadas",
  "itemListOrder": "https://schema.org/ItemListOrderDescending",
  "numberOfItems": 20,
  "itemListElement": [
    { "@type": "ListItem", "position": 1,
      "url": "https://radio.gofestivals.eu/es/stations/hardtechno-radio-berlin",
      "name": "HardTechno Radio Berlin" }
  ]
}
```

**(e) FAQPage en hubs**: 2-4 preguntas de plantilla+datos. *Impacto honesto*:
rich result de FAQ restringido desde 2023 a sitios de alta autoridad — el
valor real es el contenido longtail indexable.

**(f) MobileApplication: NO.** No existe app nativa y la PWA está pendiente.
Marcar una app inexistente es spam de schema. Cuando la PWA sea instalable,
valorar `WebApplication`.

---

## 5 · Sitemaps

Escala actual (~2.700 entradas) cabe holgadamente en **un** sitemap (límite
50k). Sin sobre-ingeniería todavía.

**Fase 1 — extender `buildSitemapEntries`** (`lib/sitemap-data.ts`):
- Añadir `/countries`, `/countries/{iso2}` (desde facetas, respetando gate),
  `/trending`(+género), `/new`, `/search`. Entran gratis en `sitemap.ts` Y
  `sitemap-v2.xml` (se conserva el truco GSC: ambos consumen la misma fuente).
- **`lastmod` desde `updated_at`**: exponerlo en el API y pasarlo — la señal
  de recrawl más útil. Para hubs: max(updated_at) de sus emisoras.
- Prioridades: home 1.0 · hubs 0.8 · combos/trending 0.7 · emisoras 0.6 ·
  estáticas 0.3.
- **Fix x-default** (decidido: `en`, coherente con `lib/seo.ts`; mercado top
  DE/US/GB).

**Fase 2 — índice de sitemaps cuando >10k URLs** (catálogo >4-5k emisoras),
con `generateSitemaps()`:

```
/sitemap.xml                    (índice)
  ├── /sitemap/static.xml
  ├── /sitemap/genres.xml
  ├── /sitemap/countries.xml    países + combos
  ├── /sitemap/stations-0.xml   chunks de 10k
  └── /sitemap/stations-1.xml
```

Beneficio: cobertura *por tipo* visible en GSC — la métrica de diagnóstico
clave de un sitio programático.

---

## 6 · SEO técnico

**Paginación y filtros en `/genres/[slug]`** (`?country=&page=`):
- `rel=prev/next` muerto desde 2019. Decisión: **`?page=N` self-canonical e
  indexable**, title diferenciado ("… — página {N}") y paginación con
  `<a href>` reales (no botones). Las páginas profundas contienen emisoras no
  enlazadas desde ningún otro sitio — noindex las dejaría solo en el sitemap.
- `?country=XX`: canonical al combo dedicado cuando exista y pase el gate; si
  no, canonical a la página 1 limpia del género.

**Robots meta en auth/cliente**: el disallow de robots.txt **no impide la
indexación** de URLs enlazadas. Añadir `robots: { index: false }` en
login, signup, forgot-password, reset-password, profile, favorites,
verify-email (este último falta también en robots.ts).

**ISR**: estrategia actual correcta; hubs nuevos a 300s, `/trending` a
300-900s.

**Core Web Vitals**: sin imágenes, el LCP es texto → la fuente es el cuello
de botella. **Migrar Fontshare del `<link>` CDN a `next/font/local`**
(elimina conexión a terceros, `font-display` controlado, preload automático).
Mejor ratio esfuerzo/impacto en CWV del proyecto. CLS: reservar altura del
player global y los grids.

**OG images**: hoy cero imágenes = card vacía al compartir en Discord/
Telegram (donde vive la audiencia electrónica). `opengraph-image.tsx` con
`ImageResponse` (edge, sin assets): emisora (nombre + avatar iniciales +
género + país) y género (nombre + contador).

**Otros**: `/search?q=` parametrizado → noindex (solo `/search` limpio
indexable como target del SearchAction).

---

## 7 · SEO internacional

**Subdirectorios — mantener** (decisión firme):
- ccTLDs fragmentarían una autoridad que aún no existe y multiplican ops
  (certificados, GSC, sitemaps) — inviable para un solo dev.
- Subdominios heredan autoridad peor que subdirectorios en la práctica.
- Subdirectorios concentran el link equity, GSC único con filtros por
  carpeta, y next-intl ya lo gestiona (`localePrefix: always`).

**Roadmap de locales**: 1) **`de` primero** — país top del catálogo Y mayor
mercado techno de Europa; 2) `fr`; 3) `pt` (Brasil: mercado enorme,
competencia baja). Mecánica: añadir a `LOCALES` en `lib/seo.ts` +
`sitemap-data.ts` + next-intl + `messages/{locale}.json`; hreflang y sitemap
se actualizan solos. **Antes de `de`: fix x-default** para no propagar el
error. Contenido **localizado, no traducido**: variantes por locale con giros
propios en las plantillas de intro/FAQ.

---

## 8 · Estrategia de contenido (ventaja injusta: datos propios + ecosistema)

1. **Guías por género** (~20, ritmo 2/mes): "Qué es el techno melódico:
   historia, artistas y las mejores radios". 800-1.500 palabras, terminan en
   el ItemList del hub → captura el cluster informacional y bombea autoridad
   al hub programático.
2. **Rankings mensuales con datos reales** desde click_trend/plays — nadie
   más en el nicho tiene datos de escucha de directorio.
3. **Estudio anual "Estado de la radio electrónica"** desde catálogo +
   now_playing (países por género, géneros en crecimiento, tracks más
   radiados) → el activo de PR de datos del §9.
4. **Tie-ins de temporada de festivales** con cross-links gofestivals.eu/.es
   ("¿Vas a Time Warp? Las radios para entrenar el oído"). Calendario pegado
   a la temporada (marzo-septiembre).
5. **Fichas top-50 enriquecidas** con párrafo editorial único.

Sin blog separado al inicio: las guías viven en los hubs de género (concentra
señales en la URL que ya rankea). Sección `/blog` cuando haya >10 piezas.

---

## 9 · Link building (por ROI)

1. **Cross-links del ecosistema gofestivals** (ROI máximo, coste ~0): página
   de cada festival → "radios del género de este festival". Mismo owner,
   contextual, legítimo.
2. **Badge/widget "Escúchanos en"** (el arma clásica de los directorios):
   página `/for-stations` con snippet embed (badge SVG + mini-player iframe)
   que enlaza a la ficha. Outreach a las 1.259 emisoras (contacto en su
   homepage vía Radio-Browser). Tasa realista 3-8% → **40-100 enlaces de
   dominios temáticamente perfectos**.
3. **PR de datos** (estudio del §8.3): Resident Advisor, Mixmag, DJ Mag,
   Groove.de, r/techno. 1 campaña/año.
4. **Comunidades** (genuino, no spam): r/techno, foros de DJs, Discords de
   sellos — nofollow pero tráfico semilla y señales de marca.
5. **Directorios** / ProductHunt (lanzamiento PWA) / awesome-lists. Cola
   larga.

---

## 10 · Roadmap

### 0-30 días — fundaciones + quick wins
| Acción | Archivos |
|---|---|
| Fix x-default inconsistente | `apps/web/src/lib/sitemap-data.ts` |
| noindex meta en auth/cliente + verify-email en robots | páginas auth + `robots.ts` |
| Fix BreadcrumbList último ítem | `stations/[slug]/page.tsx` |
| Fontshare → next/font/local | `[locale]/layout.tsx`, fuentes locales |
| **Backend: facetas + trending + new** | `repos/stations.py`, `api/v1/stations.py`, schemas |
| OG images dinámicas | `opengraph-image.tsx` en stations y genres |
| Cross-links desde gofestivals.eu/.es | (repos del ecosistema) |

### 30-90 días — capa programática fase 1
/countries + /countries/[code] (gate ≥3) · /trending(+género) · /new ·
enlaces ascendentes en fichas · sitemap con rutas nuevas + lastmod ·
/search + SearchAction · paginación con `<a href>` + titles "página N".

### 90-180 días — combos + contenido + locale de
/countries/[code]/[genre] (gate ≥5) + canonicals de `?country=` · FAQPage en
hubs · primeras 6-8 guías de género · primer ranking mensual · `/for-stations`
+ outreach ola 1 (300 emisoras) · **locale `de`** · BroadcastService en fichas.

### 180+ días
/languages (tras normalizar el campo language en backend) · estudio anual +
PR · crecer catálogo (+1.000 emisoras con health-check de stream previo) ·
índice de sitemaps por tipo (>10k URLs) · locales fr/pt · revisitar ciudades
(solo si Berlín/Londres ≥10 emisoras) · PWA → WebApplication + ProductHunt.

---

## 11 · Priorización

| Acción | Impacto | Coste | Tiempo | ROI |
|---|---|---|---|---|
| Endpoints de facetas (prereq) | — (desbloquea) | Bajo | 1-2 d | ⭐⭐⭐⭐⭐ |
| Páginas de país (gate ≥3) | Alto | Medio | 3-4 d | ⭐⭐⭐⭐⭐ |
| Combos país×género (gate ≥5) | **Muy alto** | Medio | 3-4 d | ⭐⭐⭐⭐⭐ |
| Badge/widget + outreach | Alto (enlaces) | Medio | 3 d + continuo | ⭐⭐⭐⭐⭐ |
| Cross-links ecosistema | Medio | Muy bajo | 0,5 d | ⭐⭐⭐⭐⭐ |
| Fixes higiene (x-default, noindex, breadcrumb) | Medio | Muy bajo | 0,5 d | ⭐⭐⭐⭐⭐ |
| Trending + new | Medio-alto | Bajo | 2 d | ⭐⭐⭐⭐ |
| OG images | Medio (CTR social) | Bajo | 1 d | ⭐⭐⭐⭐ |
| next/font (CWV) | Medio | Bajo | 0,5 d | ⭐⭐⭐⭐ |
| Sitemap lastmod + rutas | Medio | Bajo | 1 d | ⭐⭐⭐⭐ |
| Locale `de` | Alto | Medio | 4-5 d | ⭐⭐⭐⭐ |
| Guías de género (20) | Alto a 12 meses | Alto | continuo | ⭐⭐⭐ |
| /search + SearchAction | Bajo-medio | Medio | 2 d | ⭐⭐⭐ |
| PR de datos | Alto si funciona | Alto | 1-2 sem | ⭐⭐⭐ |
| FAQPage + BroadcastService | Bajo | Bajo | 1 d | ⭐⭐ |
| Idiomas, fr/pt, ciudades | Bajo hoy | Medio | — | ⭐ (diferir) |

---

## 12 · Top-50 oportunidades (orden de ejecución)

1. Endpoints de facetas countries (FastAPI) · 2. Endpoint trending por
click_trend · 3. Endpoint new stations · 4. Fix x-default
seo.ts/sitemap-data.ts · 5. noindex meta en 7 páginas auth/cliente ·
6. verify-email a robots.ts · 7. Fix item URL en BreadcrumbList de emisora ·
8. Fontshare → next/font/local · 9. OG image emisoras · 10. OG image géneros ·
11. Cross-links desde gofestivals.eu · 12. Cross-links desde gofestivals.es ·
13. /countries índice · 14. /countries/[code] con gate ≥3 · 15. Intros
plantilla i18n data-driven para países · 16. /trending global ·
17. /trending/[genre] gated · 18. /new · 19. Sitemap: rutas nuevas ·
20. Sitemap: lastmod desde updated_at · 21. updated_at en schema del API ·
22. Links género/país clicables en ficha · 23. Similares server-rendered
(verificar) · 24. Paginación con anchors reales · 25. Titles "página N" ·
26. /search page · 27. SearchAction en WebSite · 28. noindex en /search?q= ·
29. /countries/[code]/[genre] gate ≥5 · 30. Canonical de ?country= al combo ·
31. Filtro país del sidebar → ruta dedicada · 32. FAQs plantilla en hubs de
género · 33. FAQs en hubs de país · 34. FAQPage JSON-LD ·
35. BroadcastService+ListenAction en fichas · 36. ItemList en trending ·
37. Locale de: messages + LOCALES · 38. Plantillas de copy de para hubs ·
39. Página /for-stations con badge embed · 40. Outreach ola 1 (300 emisoras) ·
41. Guías de género 1-4 (techno, house, dnb, trance) · 42. Primer ranking
mensual publicado · 43. Párrafos editoriales en top-50 fichas ·
44. Normalización backend del campo language · 45. /languages gated ≥10 ·
46. Estudio "Estado de la radio electrónica" + PR · 47. rb_sync +1.000
emisoras con health-check · 48. generateSitemaps() índice por tipo ·
49. Locale fr · 50. Revisitar páginas de ciudad.

---

## KPIs y verificación

- Por PR: gates del repo (pytest/ruff/mypy/vitest/tsc/build + CI + nightly
  E2E).
- Fase 0-30: auth pages con meta noindex verificable; sitemap y páginas con
  el MISMO x-default; Rich Results Test limpio en fichas; Lighthouse
  antes/después del cambio de fuentes.
- Programático: test que compara facetas vs sitemap (solo páginas que pasan
  el gate); cobertura por tipo en GSC tras cada deploy.
- Trimestral: impresiones/clicks GSC por carpeta (/genres vs /countries vs
  /stations), % indexación por tipo, posiciones del cluster género×país.
