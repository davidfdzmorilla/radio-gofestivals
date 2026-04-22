# Dirección C · Sticker mixtape

## 1 · Concepto

**Carpeta del DJ con pegatinas, mixtape compartida entre amigos, energía
de web Tumblr 2012 tratada con cuidado de 2026.** Referencias claras:
- `boilerroom.tv` (pre-rediseño 2023) + `itschillas.com` / maker sites
  de la escena rave contemporánea con personalidad descarada.
- **Recent Work Book** (archivo de trabajos gráficos): superposiciones
  rotadas ligeras, elementos con rotación fija `-2deg` o `3deg`,
  sensación de "cosas pegadas unas encima de otras" sin caer en caos.
- Los stickers de la carpeta del DJ en una maleta de vinilos.

El "juguetón" aquí es **explícito pero disciplinado**: hay rotaciones
ligeras en badges y elementos secundarios, bordes gruesos con el color
del logo (`--wave`) como marco, toques de tipografía variable,
micro-easter eggs tipo "hover para hacer guiñar al personaje del logo".

Nunca cae en `rotate(-15deg)` (mareo), nunca satura con más de 3
elementos rotados visibles a la vez, y nunca rompe la legibilidad del
contenido central. La rotación decora los **bordes** — badges, stamps,
labels — pero el contenido principal se mantiene vertical y legible.

Esta es la dirección más "juguetón explícito" del trío. Más alegría
que las otras dos. Más arriesgada también.

## 2 · Tipografía

**Display: `Chillax`** (Fontshare, free commercial)
- Sans con personalidad blando-geométrica, variable entre 200-700.
- Las curvas tienen una ligera "inflación" — las "o" y "e" se sienten
  amistosas sin ser infantiles.
- NO es Space Grotesk: Chillax tiene terminales muy redondeadas y un
  carácter casi post-Satoshi, con más juego.
- Elegida porque el contexto "música para salir" no quiere rigidez —
  Neue Machina (dirección B) sería demasiado seria aquí.

```
     Chillax (Semibold 600)
     "radio.gofestivals" 72px
     La "g" con cola amplia y redonda
     La "f" con barra horizontal ligeramente más alta
     Se siente caliente, no industrial
```

**Body: `Satoshi`** (Fontshare, free commercial)
- Sans contemporánea neutral para párrafos.
- Pesos 400 y 500. Lo justo.
- Deliberadamente "menos carácter" que el display para que Chillax
  destaque. El body hace de "fondo neutral" donde Chillax y los
  acentos cantan.

**Mono: `JetBrains Mono`** (Apache 2.0)
- Sólo para metadata técnica. En esta dirección la pongo `italic` en
  los bitrates y timestamps — le da el gesto de "nota garabateada".

## 3 · Color tokens

```css
/* Background — menos oscuro que A y B, más "cálido" */
--bg-0:  #141310;  /* el --ink original intacto como base */
--bg-1:  #1c1a16;
--bg-2:  #26221d;  /* cards */
--bg-3:  #332e28;  /* hover + stickers */

/* Foreground — cálido warm-white */
--fg-0:  #fdf9ef;  /* títulos. 15.8:1 ✓ AAA */
--fg-1:  #ddd2bc;  /* body. 10.5:1 ✓ AAA */
--fg-2:  #8f867a;  /* labels. 4.9:1 ✓ AA normal */
--fg-3:  #4b463f;  /* borders/dividers (non-text) */

/* Accents — los 3 del logo, pero CON sus variantes "soft" para
   backgrounds de pills/stickers */
--magenta:      #e62de9;   /* 6.2:1 ✓ AA */
--magenta-soft: #3d0e3e;   /* background de sticker, texto fg-0 encima: 11.4:1 ✓ AAA */
--cyan:         #1cc1f9;   /* 7.9:1 ✓ AAA */
--cyan-soft:    #0b3b4f;   /* 11.0:1 ✓ AAA con fg-0 */
--wave:         #8b4ee8;   /* 4.6:1 ✓ AA */
--wave-soft:    #2a1640;   /* 12.1:1 ✓ AAA */

/* Sticker border: 2px solid del accent correspondiente */
--sticker-shadow: 0 2px 0 var(--wave);  /* sombra "offset" estilo pegatina */
```

### Reglas de aplicación

- Los 3 accents (`magenta`, `cyan`, `wave`) tienen cada uno un gemelo
  `*-soft` de fondo oscuro para **stickers, badges, pills con texto
  legible**. Nunca texto `--magenta` sobre `--magenta-soft` (contraste
  insuficiente) — siempre `--fg-0` sobre los `-soft`.
- Las rotaciones se aplican a **badges y stickers**, nunca a cards
  principales ni texto corrido.
- La `--sticker-shadow` (offset 0/2/0 sin blur) simula el peso de
  pegatina pegada. Reforzada por borde 2px del mismo color.

## 4 · Composición

### Home
Hero tipo "portada de mixtape": "radio.gofestivals" en Chillax
Semibold 88px, con un **sticker rotado -4deg** al final de la línea
con texto "N°42" en fondo `--magenta-soft`, como si fuese número de
edición. Debajo tagline en Satoshi normal, y 2-3 "sellos" (badges
sticker) rotados ligeramente: `CURATED 2026`, `ES · EN`, `ELECTRONIC
ONLY`.

Géneros en grid 3×3. Cada card es un **"sticker"**: fondo `--bg-2`,
borde 2px `--wave` inicial (cambia al color del género al hover),
`--sticker-shadow`. El nombre en Chillax 24px, conteo en mono
italic a la derecha.

"Destacadas": grid 3 columnas de cards con rotación **aleatoria
determinista** por id (`rotate(-1.2deg)` o `rotate(0.8deg)`, máximo
±2deg). Las cards se pisan ligeramente (margin negativo sutil) para
reforzar el efecto "apiladas sobre una superficie".

### Genre page
Header con un **bloque de color del género rotado -2deg** como
fondo del título. El nombre del género en Chillax 84px,
contrastando en negro o blanco. Debajo, el conteo en mono italic
pequeño. La sidebar de filtros es un "sticker" vertical pegado al
borde izquierdo con shadow offset.

### Station detail
Cover grande con rotación **-1deg** sutil + sticker shadow gruesa
(offset 0/4/0 en `--wave`). El nombre en Chillax al lado sin rotar
(contenido principal vertical siempre). Badges como stickers
pequeños rotados distintos ángulos (-3, 2, -1.5). "Sonando ahora"
como un post-it `--cyan-soft` con rotación -1deg.

### GlobalPlayer
Bottom fixed, 80px alto, fondo `--bg-0` con borde top 3px `--wave`.
El play button es un "sticker circular" grueso con shadow offset. Al
hover, se "despega" (translate -2px + shadow aumenta).

### Grid cards
- 3 columnas desktop, 2 tablet, 1 móvil
- Gap 24px (más generoso, las rotaciones necesitan espacio)
- Card radius 12px (más redondeado, sticker feel)
- Rotación determinista por `station.id` (pseudo-random pero
  consistente entre renders)

## 5 · Microanimaciones

Duración **200ms** con easing **cubic-bezier(0.34, 1.56, 0.64, 1)**
(ease-out-back sutil con micro-bounce).

1. **Sticker shake en play button al iniciar stream**: rotate(-2deg) →
   rotate(2deg) → rotate(0deg), 300ms total. Pequeño gesto "me has
   despertado". **Animación firma**.
2. **Hover de station card**: translateY(-3px) + rotate(0deg) (se
   endereza si estaba rotada). Se siente como "levantar la pegatina".
   Al salir, vuelve a su rotación asignada.
3. **Now-playing track change**: fade out antiguo (translateY -4px +
   opacity), 180ms. Nuevo entra (translateY 4px → 0 + opacity), 180ms
   con delay 60ms. Similar a A pero más suelta (el ease-out-back le
   da micro-bounce).
4. **Sticker stagger en grid reveal**: 12 cards aparecen con rotación
   + opacity. Cada una con delay incremental de 60ms. Total ~720ms.
5. **Locale switcher**: al abrir dropdown, aparece con rotation-start
   de `rotate(-1deg) scale(0.98)` → estado final, 200ms. Se siente
   como una pegatina que se despega del menú.
6. **Easter egg sutil**: el logo-icon (el bailarín del SVG) hace un
   **micro-wiggle** (rotate -3deg → 3deg → 0, 400ms) cuando hay track
   change global. Sutil, visible solo si miras el logo.

## 6 · Riesgos

- **Rotaciones pueden cansar**. Ley dura: máximo 3 elementos rotados
  visibles en viewport. Si añadimos 12 cards rotadas con stagger,
  perdemos. Solución: rotación aplica solo a **cards curadas** (max
  6-12) y **nunca** en mobile (<768px).
- **Shake del play button** puede ser molesto en cliente con
  `prefers-reduced-motion`. Obligatorio: respetar prefers-reduced-motion
  globalmente (`animation: none`).
- **Accesibilidad**: elementos rotados pueden confundir a lectores de
  pantalla si overlapping crea oclusiones. Hay que asegurar `z-index`
  explícito y que el `tab-order` no dependa de posiciones visuales.
- **Percepción de "poco serio"**: esta dirección es la que más puede
  alienar a audiencias profesionales (programadores de clubes,
  bookers). Contrapunto: el público objetivo NO es el booker, es el
  usuario final que quiere disfrutar; y las rotaciones son ±2deg, no
  ±15deg, no es infantil.
- **Chillax** está menos probada en producción que Neue Machina o
  Fraunces. Calibrar carefully el rendering sub-pixel en Chromium
  vs Safari (a veces los sans redondeados se ven bold-ish en Safari).
- **Reversibilidad**: la tipografía y color son fáciles. Las
  rotaciones son CSS — también fáciles. El **concepto "sticker"** está
  tejido en muchos componentes, deshacerlo implicaría un segundo pase
  de cleanup.
- **Coste tipográfico**: Chillax + Satoshi + JetBrains Mono ≈ 120KB
  con subset. El más ligero de los tres.
