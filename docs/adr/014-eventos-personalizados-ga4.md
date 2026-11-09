# ADR 014 · Eventos personalizados de GA4

## Contexto

GA4 (ADR 013) solo mide páginas vistas y clics salientes. No responde si se escucha, si
las emisoras fallan ni si mandamos tráfico a gofestivals. Las reproducciones ya se guardan
en nuestra API (`recordPlay`, a los 30 s): esa es la fuente de verdad de cifras absolutas.

## Decisión

`trackEvent()` (`lib/analytics.ts`) envía eventos tipados (unión cerrada) a `window.gtag` y no
hace nada si GA no está cargado, de modo que el consentimiento se aplica una única vez al
cargar el script. Primera tanda: `play_start` (en `player-store.play`), `play_30s` y
`play_error` (en `GlobalPlayer`, este solo cuando fallan todos los streams),
`festival_outbound` (`TrackedAnchor` en `FestivalHero`) y `favorite_add` (`HeartButton`).
`source` se deriva de la ruta (`pageSource`). Sin texto libre, sin identificadores de cuenta.

## Consecuencias

- (+) Embudo escucha → error → salida a festival con `source`, `genre`, `country`.
- (+) `play_error` detecta emisoras rotas desde el lado del usuario.
- (−) Los números de GA infravaloran (solo quien acepta, bloqueadores) y no cuadran con la BD.
- (−) Para usar los parámetros en informes hay que registrarlos como dimensiones personalizadas
  en GA (`source`, `genre`, `country`, `destination`, `placement`) y marcar `play_30s` y
  `festival_outbound` como key events.
- Texto de privacidad actualizado para mencionar las interacciones medidas.
- Pendiente (no medido a propósito): `play_stop`, `locale_change`, `badge_snippet_copy`.

## Atribución y valores (T5, 9 nov 2026)

- GA se carga tras aceptar el banner. Si el visitante llegó desde Google o con `utm_*` y navegó
  antes de aceptar, la sesión empezaba en una página sin utm y sin referrer útil (directa o "sin
  asignar"). Ahora `GoogleAnalytics` guarda **solo en memoria** la página y el referrer de entrada
  (`window.__rgfLanding`, nada en storage ni red hasta aceptar) y, al aceptar, abre la sesión con
  un `page_view` de la entrada (`page_location` con los utm, `page_referrer`) seguido del de la
  página actual. Si se acepta en la propia entrada, queda el `page_view` automático.
- `?ga_debug=1` en la URL de entrada activa DebugView.
- Los valores de `genre` y `country` van siempre en minúsculas (GA distingue `DE` de `de`).
- Comprobado: no hay Measurement Protocol (ni backend ni worker), `config` va siempre antes de
  cualquier `event` (sin `gtag`, `trackEvent` no hace nada) y no se usa Consent Mode.
