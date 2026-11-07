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
