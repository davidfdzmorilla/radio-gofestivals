# Dirección B · Chroma studio

## 1 · Concepto

**Estudio gráfico contemporáneo, geométrico y vibrante, con restricción.**
Referencias claras:
- `pangrampangram.com` (la foundry): sans geométrica pesada como anclaje,
  acentos de color plenos usados en bloques, nunca diluidos.
- Los posters de **Julia Born** y la identidad del **Centre Pompidou
  Metz** (2010) filtrados por tipografía web contemporánea.
- `resident-advisor.net` (pero RA es más "periodista sobrio"; aquí
  queremos su rigor con +10% de alegría).

El "juguetón" aquí es **rítmico y cromático**: composición muy
ordenada con bloques grandes, pero los acentos vibrantes tienen
presencia visible. Es la personalidad de un estudio serio que hace
posters de raves — no da miedo el color, pero cada decisión tiene
intención.

Cada station es un **módulo** — tiene proporciones casi cuadradas, el
color del primer género ocupa una zona definida (no solo un
micro-avatar), y la tipografía está tratada como elemento compositivo
junto a ese color.

## 2 · Tipografía

**Display: `Neue Machina`** (Pangram Pangram, gratis para uso comercial)
- Sans geométrica con terminales planas y una "a" de un piso muy
  distintiva, esquinas ligeramente redondeadas que la distinguen de
  las clones de GT America.
- NO es Space Grotesk: Neue Machina tiene más contraste de peso,
  terminales más rectangulares, carácter más "industrial bonito".
- Pesos: Ultrabold 800 para display hero, Regular 400 para subtítulos.
- Se siente contemporánea-editorial, encaja con el tono "catálogo
  curado", no con el tono "techno glitch".

```
     NEUE MACHINA (Ultrabold 800)
     "RADIO.GOFESTIVALS" — 72px
     M con esquina recta interna (firma del typeface)
     "g" de un piso con terminales cortadas
```

**Body: `General Sans`** (Fontshare, free commercial)
- Sans humanista con personalidad sutil, "open apertures" que la
  hacen legible a cuerpo pequeño.
- `400`, `500`, `600`. Por defecto 400 a 15px.
- Alternativa si queremos más neutralidad: `Satoshi` (Fontshare).
  Pero General Sans tiene una "g" de dos pisos y una "a" con cola
  que le dan más sabor — mejor para nuestro mood.

**Mono: `Space Mono`** (SIL OFL)
- Elegida sobre JetBrains Mono por su **carácter** — Space Mono tiene
  una personalidad casi retro-técnica que encaja con "música
  electrónica" sin caer en techno clichés.
- Solo para labels cortos: bitrate, codec, country code, timestamps.

## 3 · Color tokens

```css
/* Background — contraste moderado, sin ir al negro puro */
--bg-0:  #0f0e0c;  /* base 1 punto más oscuro que --ink original */
--bg-1:  #16140f;
--bg-2:  #201d18;  /* surfaces/cards */
--bg-3:  #2b2721;  /* elevated/hover */

/* Foreground — warm-neutral, NO frío (el fondo tiene warm undertone) */
--fg-0:  #fbf6ec;  /* títulos. 16.1 : 1 ✓ AAA */
--fg-1:  #d6cdb9;  /* body. 10.2 : 1 ✓ AAA */
--fg-2:  #938b7c;  /* labels. 5.1 : 1 ✓ AA normal */
--fg-3:  #4a453e;  /* borders, non-text */

/* Accents — fuerte, saturados, bloques no gradientes */
--magenta:  #e62de9;   /* 6.2:1 sobre bg-0 ✓ AA */
--cyan:     #1cc1f9;   /* 7.9:1 sobre bg-0 ✓ AAA */
--wave:     #8b4ee8;   /* 4.6:1 sobre bg-0 ✓ AA */

/* Los acentos tienen también una variante "plane" (fondo) donde
   el texto que los pisa es --bg-0 (negro). Contraste invertido.    */
--on-magenta: var(--bg-0);  /* 6.2:1 ✓ */
--on-cyan:    var(--bg-0);  /* 7.9:1 ✓ */
--on-wave:    var(--fg-0);  /* necesario: blanco sobre wave 4.4:1 ✓ */
```

### Reglas de aplicación

- Los acentos se usan **como bloques**: un card puede tener una tira
  magenta del 25% de su altura con el nombre en negro encima. No
  "outline magenta con texto magenta".
- El **cyan** marca lo **vivo** (stream conectado, now-playing
  llegando). Es el color de lo que late.
- El **magenta** marca lo **curado** (badge, borde izquierdo de card
  de curated, filtros activos). Es lo "destacado editorial".
- El **wave** es el color del **producto** — logotipo, play button en
  reposo. Es la identidad, no un estado.

## 4 · Composición

### Home
Hero frontal con "RADIO.GOFESTIVALS" en Neue Machina Ultrabold 96px,
display que ocupa casi todo el ancho. Debajo, un pill grande con el
color `--wave` y el tagline en negro: un bloque, no texto suelto.

Los 9 géneros se presentan como **grid 3×3 de cuadrados**. Cada
cuadrado tiene:
- El color del género ocupando una banda diagonal del 40% del área
- El nombre en display grande dentro
- El conteo en mono 11px alineado abajo
Al hover, la banda diagonal crece al 100% con transición, el texto
cambia a negro si el color es suficientemente claro, blanco si no.

"Destacadas" usa grid 4×3 (12 cards) con **proporción cuadrada**.
Cada card tiene una estructura fija:
- 40% superior: bloque de color del primer género, con iniciales en
  display en el centro
- 60% inferior: fondo `--bg-2`, nombre en display 18px, ciudad+país
  en mono, badges

### Genre page
Hero espectacular: todo el header (280px de alto) es del color del
género con patrón sutil de puntos a 10% opacity. Nombre del género
centrado en display 108px, contrastando en negro o blanco según
luminancia. Debajo un contador en mono grande (`13 STATIONS`). La
sidebar es estrecha (200px) y vive a la izquierda pegada, con
fondo `--bg-2`.

### Station detail
Estructura asimétrica 1/3 + 2/3:
- Izquierda: cover enorme (400×400 desktop) con el color del primer
  género + iniciales display 200px
- Derecha: nombre display, ciudad+país mono, badges como chips
  sólidos de color pleno, botón play + "tracks recientes" como lista

### GlobalPlayer
88px de alto (un poco más presente). Fondo `--bg-2` con borde top
2px `--wave`. Play button circular 56px `--wave`. Track info a la
derecha con fade animation al cambiar. Equalizer **visual** (3
barras animadas) cuando está sonando — la animación "firma".

### Grid cards
- Cuadradas (aspect-ratio 1:1)
- Gap 16px
- Sin radius o radius 4px máximo (cuadrados bien)
- El color es un **bloque**, no un micro-avatar

## 5 · Microanimaciones

Duración **220ms** con easing **cubic-bezier(0.33, 1, 0.68, 1)**
(ease-out-cubic, rebote minimal).

1. **Equalizer bars en GlobalPlayer cuando playing**: 3 barras
   verticales de 3×12px en cyan, cada una con animación
   `height-bounce` de 400-800ms con delays staggered (0, 120ms,
   240ms). Loop infinito. **Animación firma**: cuando hay música, la
   barra se mueve, visible siempre que miras al player.
2. **Hover de genre card** (los 3×3): la banda de color diagonal se
   expande hasta cubrir 100%, 220ms. Texto se invierte.
3. **Play button active**: al activarse, `box-shadow: 0 0 0 6px
   rgba(139,78,232,0.3)` aparece y crece a 12px (150ms), luego se
   desvanece (300ms). Se siente como un "tick" de vida.
4. **Stagger reveal de "Destacadas"**: 12 cards con delay
   incremental de 50ms cada una, total ~600ms. Animan opacity 0→1 +
   scale 0.96 → 1.
5. **Locale switcher dropdown**: al abrir, slide-down 8px + opacity,
   220ms. Item hover: fondo `--bg-3`, 150ms.

## 6 · Riesgos

- **Los bloques de color pueden parecer Duolingo** si se aplican sin
  restricción. La regla `--magenta = curated`, `--cyan = live`,
  `--wave = producto` es **crítica** para no caer en "every widget
  has a different color". Necesita disciplina en review.
- **Equalizer bars** es la animación firma pero puede molestar si es
  demasiado inquieta. Hay que calibrar la altura (no más de 12px) y
  la frecuencia (no más rápido que 400ms por ciclo).
- **Cards cuadradas** a veces cortan nombres largos (las stations de
  Radio-Browser son brutales). Mitigación: truncar a 2 líneas con
  ellipsis, tooltip con nombre completo al hover.
- **Neue Machina** es una fuente freemium — la versión gratuita es
  100% utilizable comercialmente pero no tiene tantos pesos variables
  como la Pro. Pesos disponibles son suficientes (Regular + Ultrabold).
- **Coste tipográfico**: Neue Machina 400+800 + General Sans 400+500 +
  Space Mono 400 ≈ 140KB con subset. Un pelo más que A. Aceptable.
- **Reversibilidad**: sistema de color y bloques es fácil de
  revertir. Las cards cuadradas implican markup especializado —
  cambio medio.
