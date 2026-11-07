# ADR 013 · Google Analytics 4, solo con consentimiento

Fecha: 2026-11-07

## Contexto

Queremos medir el uso del sitio (páginas vistas, origen del tráfico, dispositivos) y hemos decidido
usar Google Analytics 4 (ID de medición `G-G196JWJWLC`). El sitio es de un responsable en España y
ya tiene un banner de consentimiento (cookie `rgf_consent`, aceptar/rechazar con el mismo peso
visual) que hasta ahora cubría solo el conteo de reproducciones. La página de cookies afirmaba
expresamente que no usábamos analítica externa, y la CSP en enforce (ADR 007) solo permite
orígenes propios.

Pegar el snippet de Google tal cual en el `<head>` cargaría Google antes de que nadie elija,
contradiría los textos legales y sería bloqueado por la CSP.

## Decisión

- El snippet no va en el `<head>`: lo carga un componente cliente (`GoogleAnalytics`) **solo
  si `rgf_consent = accepted`**. Sin elección o con rechazo no se pide nada a Google. El banner
  avisa con un evento al elegir, así que se carga sin recargar la página.
- El ID se configura por entorno (`NEXT_PUBLIC_GA_MEASUREMENT_ID`, argumento de build; el compose
  usa `${GA_MEASUREMENT_ID-G-G196JWJWLC}`, y una variable definida y vacía desactiva la analítica).
  El ID se valida con una expresión regular antes de interpolarse en el script.
- Se desactivan las señales de publicidad (`allow_google_signals` y
  `allow_ad_personalization_signals` a `false`). No se envía el usuario ni las reproducciones.
- Solo en las páginas públicas (`[locale]/layout`); el panel de administración no la carga.
- CSP (Traefik): `script-src` + `https://www.googletagmanager.com`; `img-src` +
  `googletagmanager.com` y `*.google-analytics.com`; `connect-src` + los dos anteriores y
  `*.google.com`. Es el conjunto mínimo de la guía de CSP de Google para Analytics sin Ads.
- Textos: banner, política de cookies (cookies `_ga` y `_ga_G196JWJWLC`) y política de privacidad.

## Consecuencias

- (+) Cumple el consentimiento previo: antes de aceptar no hay peticiones a Google ni cookies `_ga`.
- (+) Un solo sitio donde se decide el ID y el entorno, y desactivable sin tocar código.
- (−) La medición solo cubre a quien acepta: las cifras de GA infravaloran el tráfico real (la tasa
  de aceptación suele ser claramente inferior al 100 %).
- (−) Una única decisión del banner cubre dos fines (reproducciones y analítica). Es más simple
  pero no es granular; si hiciera falta, habría que separar el consentimiento por fin.
- (−) La CSP admite ahora tres orígenes de Google; `*.google.com` es amplio. Se mantiene el
  conjunto que Google documenta como mínimo.
- (−) Hay transferencias internacionales de datos a Google; los textos legales lo mencionan y
  conviene que los revise quien lleve lo legal.
- (−) Cambiar el ID exige reconstruir la imagen web (es una variable de build).
