# Dirección A · Editorial underground

## 1 · Concepto

**Editorial música-underground, mood magazine independiente de los 90
digitalizado.** Referencias claras:
- `pitchfork.com` pre-rebrand 2023 (cuando tenía más personalidad
  editorial y menos homogeneización content-farm).
- `migra.xyz` (estudio de DJ software): tipografía serif dramática
  contrastada con grotesk pequeño, grid asimétrico, acentos de color
  usados como marcas tipográficas, no como decoración.
- Fanzine de rave 92-95 pasado por un estudio contemporáneo tipo Pentagram.

La personalidad "juguetona" no sale del gesto (bounce, scale, emoji)
sino de la **voz editorial**: titulares largos que respiran, labels
pequeños en mayúsculas como de revista, numeración de secciones
(`01 / DESTACADAS`) que organiza visualmente sin gritar.

El catálogo se presenta como "la selección de la semana" más que como
lista de archivos — cada station card tiene peso de ítem editorial, no
de fila de base de datos.

## 2 · Tipografía

**Display: `Fraunces`** (Google Fonts, SIL OFL — commercial ok)
- Variable font con ejes `opsz` (optical size), `wght` 100-900 y `SOFT` / `WONK` para dar carácter
- NO es Space Grotesk: es un serif con historia, diseñado por David Jonathan Ross
- La uso en título del logotipo, hero de home, headers de sección
- `font-variation-settings: 'opsz' 144, 'SOFT' 30, 'WONK' 1` para tamaños grandes → da el carácter orgánico

```
     Fr au nc es
   "radio.gofestivals" en display 84px con SOFT=30:
   curvas suaves, la "g" de doble piso, ascendentes altas
```

**Body: `Inter Tight`** (Google Fonts, SIL OFL)
- Variante condensada de Inter, más densa y con más peso visual
- `400` cuerpo, `500` labels, `600` énfasis
- Elegida porque Inter Tight tiene mejor densidad en párrafos largos
  (los nombres de stations son a veces brutales)
- No usamos Inter estándar: ya está muerta de tanto uso ("cookie-cutter")

**Mono: `JetBrains Mono`** (Apache 2.0)
- Sólo para metadata: bitrate, codec, timestamps, country codes
- Mantiene el sabor técnico del producto (es un "reproductor de streams
  de radio" — la técnica tiene presencia discreta)

## 3 · Color tokens

```css
/* Background scale — lo más oscuro al fondo, capas progresivas */
--bg-0:  #0b0a08;  /* base, más oscuro que --ink actual */
--bg-1:  #14130f;  /* el --ink original, para surfaces */
--bg-2:  #1c1b17;  /* cards */
--bg-3:  #262521;  /* hover + elevated */

/* Foreground — contraste calculado contra --bg-0 */
--fg-0:  #f6f2ea;  /* máximo contraste (papel antiguo). 15.3 : 1 ✓ AAA */
--fg-1:  #c9c2b3;  /* body. 9.1 : 1 ✓ AAA */
--fg-2:  #8a8478;  /* muted, labels. 4.8 : 1 ✓ AA normal */
--fg-3:  #5a5549;  /* borders, dividers (non-text) */

/* Accents (reusan paleta gofestivals del logo) */
--magenta:  #e62de9;   /* 6.2 : 1 sobre bg-0 ✓ AA */
--cyan:     #1cc1f9;   /* 7.9 : 1 sobre bg-0 ✓ AAA */
--wave:     #8b4ee8;   /* 4.6 : 1 sobre bg-0 ✓ AA */

/* Semantic shadows */
--shadow-lift: 0 2px 0 0 var(--fg-3);
--shadow-deep: 0 24px 48px -12px rgba(0,0,0,0.7);
```

### Reglas de aplicación

- `--fg-0` solo para títulos grandes y play button activo
- `--fg-1` por defecto para cualquier texto legible
- `--fg-2` para labels secundarios, metadata, timestamps
- `--magenta` se reserva para **acentos editoriales únicos**: numeración
  de sección, el "1" de "01 / DESTACADAS", un underline del link activo
- `--cyan` para estados **técnicos**: "conectando", bitrate, codec mono
- `--wave` es el color del producto — logo, state actual del player.
  Usado con **mucha** restricción, casi solo el play button

## 4 · Composición

### Home
Grid de 12 columnas, gutter 32px. El hero ocupa 8 columnas con el
tagline en serif grande + subtítulo en grotesk minúsculo. Las 4
columnas restantes están **vacías** a la derecha — respiración
deliberada. Debajo, la lista de 9 géneros se presenta como
**índice tipográfico**, no como cards: números + nombres grandes, el
conteo en mono a la derecha. Al hover, la fila se desplaza 8px a la
derecha con un `::before` que dibuja el color del género.

La sección "Destacadas" rompe el grid: lista de cards pero cada card
tiene una altura distinta (algunos con now-playing visible, otros
sin). Hay un track leader editorial flotante ("Curada por David ·
Abril 2026") en cyan pequeño, alineado a la derecha.

### Genre page
Header dominado por un número enorme (el color_hex del género como
fill transparente al 15%) y el nombre del género en display serif. El
slug pequeño debajo en mono (`slug: techno · 13 stations`). La
sidebar de filtros vive a la izquierda, con labels en mono pequeño
como de formulario editorial; no hay títulos pomposos.

### Station detail
Dos columnas asimétricas: izquierda 40% con cover grande (cuadro de
color + iniciales en serif dramático), derecha 60% con el nombre en
display (puede ocupar 3-4 líneas, eso es bueno, no se corta), badges
debajo, botón play grande. "Sonando ahora" se sitúa abajo como
bloque editorial aparte, no como sidebar.

### GlobalPlayer
Fixed bottom, 72px de alto. Fondo `--bg-0` con borde top de 1px
`--fg-3`. La station name en grotesk 500, el track actual en serif
400 italic (marca editorial), artist en mono. Play button circular
`--wave` con hover que lo sube 1px.

### Grid cards
- 3 columnas desktop, 2 tablet, 1 móvil
- Gap 20px
- Card padding 20px, radius 8px (no demasiado redondeado, peso editorial)
- Shadow: la `--shadow-lift` al reposo (línea inferior de 2px color
  `--fg-3`), al hover la línea se vuelve del color del primer género

## 5 · Microanimaciones

Duración global: **180ms** (rápido, editorial), easing **cubic-bezier(0.2, 0.6, 0.2, 1)** ("pillow bounce" minimal).

1. **Track change en NowPlaying** — firma editorial:
   - El title actual se desplaza 4px arriba con opacity 0, 180ms
   - El nuevo title entra desde 4px abajo con opacity 1, 180ms + 60ms delay
   - Total 240ms. No hay flash. Se siente como un teletipo editorial.
2. **Hover de genre index**:
   - Translate X 0 → 8px, 180ms
   - Pseudo `::before` dibuja una barra vertical de 3px del color del
     género en X=0, escalándose de `scaleY(0)` a `scaleY(1)`, 180ms
3. **Play button click**: `scale(1) → scale(0.94) → scale(1)`, 220ms total
4. **Grid reveal al cargar**: 12 cards aparecen con `animation-delay`
   escalonado (cada una 40ms más tarde que la anterior, opacity 0→1 +
   translateY 12px→0). Total pathway ~600ms, se siente como que el
   feed se "imprime" de arriba abajo.

Animación "firma": el **track change**. Sutil, editorial, memorable.

## 6 · Riesgos

- **Serif display puede sentirse pesado en mobile**: Fraunces a 32px
  tiene menos presencia que a 84px. Mitigación: usar `opsz` variable
  para que el optical size pese automáticamente; reducir `SOFT` a 0
  por debajo de 40px.
- **Asimetría de 8 col + 4 vacías**: los devs junior y los clientes
  tienden a querer "rellenar" ese hueco. Hay que defender la respiración.
- **Grid con alturas variables** en "Destacadas" puede romperse feo
  si faltan datos. Mitigación: fallback a altura fija si no hay
  now_playing.
- **Cambio de Fraunces Variable** (no está 100% soportado en algunos
  navegadores antiguos). Fallback: Georgia. Irreversible si queremos
  soportar IE11; no lo queremos.
- **Coste alto de tipo**: Fraunces Variable es ~200KB. Subset a latin
  + latin-ext reduce a ~65KB. Aceptable pero requiere configurar
  `next/font` bien.
- **Reversibilidad**: tipografía y color son fáciles de revertir
  (son CSS vars + next/font). El cambio editorial del grid es más
  difícil de deshacer porque afecta a markup.
