# CLAUDE.md · apps/web

Contexto específico del frontend Next.js 15 + App Router.

## Reglas

- **Server Components por defecto**. `'use client'` solo cuando necesitas
  estado (`useState`), efectos (`useEffect`), handlers del DOM o WebSockets.
- **Data fetching en server** con `next: { revalidate: N }`. En client solo
  WS (`useNowPlaying`) o mutaciones disparadas por el usuario.
- **Tipos siempre desde `lib/types.ts`** (inferidos de zod). No definir
  interfaces manuales de payloads del API en otros sitios.
- **Componentes < 200 líneas**. Extrae helpers o hijos si se pasa.
- **No barrel files** (`index.ts` que reexporta todo). Import directo.

## i18n (next-intl)

- **Nunca texto inline**. Todo via `useTranslations(namespace)` en client
  o `getTranslations(namespace)` en server.
- **Namespaces por feature**, no por componente (p.ej. `station`, `player`,
  `filters`). Si una clave aparece en 2 features, muévela a `common`.
- **Claves en camelCase descriptivo**: `nowPlaying`, `curatedOnly`.
- **Plurales y números con ICU format** siempre:
  `"stationCount": "{count, plural, =0 {…} =1 {…} other {# …}}"`.
- **Fechas con `formatRelativeTime` de next-intl**, no librerías ad-hoc.
- **Nueva clave** → añadir en AMBOS `messages/en.json` y `messages/es.json`
  en el mismo commit.
- **Locale default**: `es` (via `NEXT_PUBLIC_DEFAULT_LOCALE`).
- **Rutas locale-prefijadas siempre**: `/es/...` y `/en/...`.

## Estilos

- **Tailwind + shadcn/ui**. Nada de CSS modules, styled-components, etc.
- **Paleta custom** en `globals.css` como CSS vars y expuesta en
  `tailwind.config.ts` (`magenta`, `cyan`, `wave`, `ink`).
- **Ordenar clases Tailwind** con `prettier-plugin-tailwindcss` si
  instalado; manualmente: layout → box → visual → interaction.

## Player

- `usePlayerStore` (Zustand) es la única fuente de verdad para el player.
- `GlobalPlayer` renderiza `<audio>` conectado al store; NO hay otro
  `<audio>` en ningún sitio.
- Autoplay bloqueado por navegadores: play solo tras user gesture.

## Fetch del API

- `apiFetch<T>` en `lib/api.ts` es el único wrapper permitido.
- Pasa siempre un `schema` zod para validar en runtime.
- `revalidate` en server components. En client, sin revalidate
  (el store o el WS gestionan frescura).
