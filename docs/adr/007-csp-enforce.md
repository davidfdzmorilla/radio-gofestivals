# ADR 007 · Content-Security-Policy en modo enforce

## Contexto

La CSP se desplegó como `Content-Security-Policy-Report-Only` con el comentario de que
sería "la primera semana". Seguía así semanas después: sin `report-uri`, las violaciones
solo se veían en la consola del navegador, así que nadie las revisaba y la política no
bloqueaba nada. Era una cabecera decorativa.

El 2026-11-04 se midió contra producción con Chromium (Playwright) reescribiendo la
cabecera a enforce: 16 páginas públicas, `/admin`, typeahead, y reproducción en 3
emisoras. La app no carga scripts, imágenes ni fuentes de terceros (las fuentes salen de
`next/font`, autoalojadas). La única violación fue `script-src: eval`, que viene de Zod 4:
comprueba `Function("")` dentro de un `try/catch` y, si falla, usa su ruta sin JIT. Con
enforce esa comprobación falla y los datos siguen validándose (el typeahead y las listas
renderizan con la política activa).

## Decisión

Pasar la cabecera a `Content-Security-Policy` en el middleware `radio-sec-headers` de
Traefik, con exactamente la misma política que estaba en Report-Only. Se mantiene
`script-src 'self' 'unsafe-inline'` (Next inyecta scripts inline para hidratar) y
`media-src *` (los streams viven en hosts arbitrarios).

## Consecuencias

- Positivas: `frame-ancestors 'none'`, `base-uri`, `form-action` y los límites de
  `default-src` pasan a bloquear de verdad. Una inyección de recursos externos deja de
  funcionar.
- Negativas: `'unsafe-inline'` en scripts anula buena parte de la protección frente a XSS.
  Quitarlo exige nonces por request (middleware de Next + render dinámico), que no se hace
  aquí.
- Negativas: cualquier recurso externo nuevo (analítica, imágenes de emisoras, embeds)
  hay que autorizarlo en la política o se bloqueará en silencio.
- Negativas: con Zod ya no hay JIT bajo esta política (validación algo más lenta). No es
  medible en los volúmenes actuales.
- La cobertura de la prueba son las páginas listadas; no se probaron flujos con sesión
  iniciada de usuario.
