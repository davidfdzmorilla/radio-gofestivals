# Backlog de ideas y pendientes · radio.gofestivals

> Lluvia de ideas del 2026-11-05, hecha tras la auditoría completa y las tres tandas de
> maquetación. Son **ideas**, no compromisos: ninguna tiene plan ni fecha. Al decidir una,
> bajarla a su propio plan en `docs/` (alcance, criterio de éxito, riesgos) antes de tocar código.
> Esfuerzo: S = horas · M = días · L = una semana o más.
> Cifras de partida (2026-11-05): 1651 emisoras activas, 2126 URLs de stream, 20 géneros raíz,
> 9 usuarios activos (1 con email verificado), dominio de Resend verificado desde el 2026-11-04.

---

## Contexto que condiciona la priorización

- Con ~9 usuarios, lo social (perfiles, follows, comentarios) rinde poco hoy. Pesa más lo que
  atrae tráfico nuevo y lo que mejora la experiencia del visitante anónimo.
- El proyecto promete "vínculo con festivales del ecosistema". Hasta el 2026-11-05 el código web solo
  mostraba la marca. El proyecto hermano (`/home/david/compose/gofestivals`) ya tiene un plan de
  cross-links (`RADIO-CROSSLINKS-PLAN.md`) cuya Fase D, la reciprocidad en la radio, es lo de este
  bloque. La integración va por su **API HTTP pública** (ADR 009), no por su base de datos.

## 1 · Festivales (el diferenciador)

**Desbloqueada** (2026-11-05): se consume `https://api.gofestivals.es/api/festivals?genre=&upcoming=true`
(100 festivales próximos, 15 de los 20 géneros raíz de la radio con datos). Ver ADR 009 y 010.

| Idea | Valor | Esfuerzo | Notas |
|---|---|---|---|
| **Hecho**: módulo "Próximos festivales de {género}" en `/genres/[slug]` y **páginas de festival** (`/festivals`, `/festivals/[id]/[slug]`, ADR 010) | Alto | M | Fase D del plan de cross-links. Pendiente: hubs de país (`country_code` en ~78 % de los próximos), medir clics, y los 403 de S3 de gofestivals están resueltos (2026-11-07: 94 de 94 imágenes con URL responden 200; 12 festivales no tienen imagen). Imágenes de festival ya en las fichas y en el JSON-LD `Event` (2026-11-06) |
| **Hecho (lado radio, 2026-11-06)**: `GET /stations/for-genres` para que gofestivals muestre emisoras en la ficha del festival (ver `docs/gofestivals-radio-stations-handoff.md`); la integración en gofestivals la hace su agente. Pendiente en la radio: página por festival con cuenta atrás | Alto | M | Reutiliza taxonomía de géneros y páginas SEO. Limitación: no se sabe el género principal de un festival (lista de 10-30 géneros sin orden) |
| Coincidencia con el cartel: si el tema emitido coincide con un artista del cartel, insignia "en el cartel de X" | Muy alto | M-L | `pg_trgm` ya está; hay que normalizar nombres de artista |
| Emisoras cerca del festival | Medio | S | Reutiliza `/nearby` (PostGIS) |
| Widget/insignia embebible para gofestivals.eu/.es | Alto | S-M | Ya hay `BadgeSnippetGenerator` para emisoras; devuelve tráfico a gofestivals |

## 2 · Descubrimiento

| Idea | Valor | Esfuerzo | Notas |
|---|---|---|---|
| "Ahora en directo": pared con lo que suena en las 50 emisoras top | Alto | S-M | Datos ya sondeados cada 60 s (ambient) |
| "¿Quién pone X ahora?": búsqueda por artista/tema sobre el historial de now-playing | Alto | M | Diferencial; `pg_trgm` |
| Colecciones editoriales (Warm-up, After, Para trabajar) gestionadas en el admin | Medio | M | También son páginas SEO |
| Ruleta / "sorpréndeme" por género | Bajo-medio | S | |

## 3 · Experiencia de escucha

| Idea | Valor | Esfuerzo | Notas |
|---|---|---|---|
| Failover de stream: si cae mientras suena, pasa a otro espejo | Alto | S-M | 2126 URLs para 1651 emisoras; selector ya deduplica espejos |
| Media Session API + PWA instalable | Alto en móvil | S-M | **Comprobar antes qué existe ya** |
| Enlaces del tema que suena a Beatport/Spotify/YouTube (búsqueda, sin API) | Medio | S | |
| Botón "este stream no va", que alimenta el health-check | Medio | S | Reutiliza el pipeline de estados |
| Heartbeat de escucha (ya previsto en la Fase 2 de `recommendations-plan.md`) | Alto | S-M | Sin él no se miden las recomendaciones |

## 4 · Presencia visual

| Idea | Valor | Esfuerzo | Notas |
|---|---|---|---|
| **Hecho**: logos reales (og:image/favicon de la web de la emisora) servidos por proxy de imágenes con caché; cron 04:50 `fetch-logos` | Muy alto | M | Reutilizar `url_guard` (ADR 008); exige abrir `img-src` en la CSP (ADR 007) o servir desde el propio dominio |
| Tarjeta para compartir "ahora suena" | Medio | S | Ya hay imágenes OG por emisora |

## 5 · Crecimiento

| Idea | Valor | Esfuerzo | Notas |
|---|---|---|---|
| Páginas de artista a partir del historial ICY | Alto (SEO cola larga) | M-L | Con las barreras anti-contenido-pobre del `seo-plan.md` |
| Boletín semanal (nuevas emisoras, tendencias) | Medio | S-M | Resend funciona; hace falta reverificar a los usuarios (1 de 9 verificado) |
| Alemán y neerlandés (mercados fuertes de electrónica) | Alto | M | Coste en traducciones, no en código |
| Feed RSS/JSON de emisoras nuevas | Bajo | S | Sobre `/export` y `/new` |
| Programa para dueños de emisoras (reclamar ficha, editar logo/descripción) | Medio | M-L | Parte de `for-stations` |

## Selección propuesta (orden sugerido)

1. Festivales (radio del festival + widget + cerca del festival).
2. ~~Logos reales con proxy cacheado~~ (hecho).
3. "Ahora en directo" + búsqueda por tema.
4. Failover de stream + Media Session.
5. Heartbeat de escucha.

## Decisiones tomadas

- **Sentry descartado** (2026-11-05, decisión de David). El warning `sentry_not_configured` del API
  es esperado. La observabilidad se apoya en logs + alertas Telegram (ADR 006) y la alerta de
  fallo de envío de email.

## Pendiente de la auditoría (2026-11-04/05)

Lo ya cerrado: disco y logrotate, Resend, Next.js (audit limpio), CSP en enforce (ADR 007),
WebSocket y refresh anónimo, hidratación de la búsqueda, tres tandas de maquetación, guard SSRF
(ADR 008).

- [ ] **Umbral de cobertura en CI**: no hay `--cov` ni `fail-under`; se desconoce la cobertura real.
- [ ] **Validar `stream_url` al importar** en `rb_sync`, para no guardar URLs internas.
- [ ] **DNS rebinding** en el guard SSRF: se resuelve en el guard y httpx vuelve a resolver al
  conectar. Cerrarlo exige fijar la IP en el backend de red (atributos privados de httpx).
- [ ] **`streams[].url` expuesto** en `GET /api/v1/stations/:slug`, contra el principio del
  CLAUDE.md ("la stream URL nunca se expone directo al navegador"). Decidir si es intencional
  (selector de calidad, analizador de espectro) y actualizar el CLAUDE.md, o dejar de exponerla.
- [ ] **Usuarios sin verificar**: 8 de 9 nunca recibieron el email (dominio sin verificar hasta el
  2026-11-04). Decidir si se les reenvía.
- [x] **Limpieza de ramas locales** ya mergeadas (2026-11-07; queda `feat/genre-editorial-techno`, sin fusionar).
- [ ] **Segunda comprobación de logs** de `health-check` tras el guard SSRF: confirmar que el cron de
  las 6 h no marca como rotas emisoras legítimas.
- [ ] **Hueco en la cabecera de la ficha** de emisora en escritorio (mitad derecha vacía): se
  mantuvo el ancho actual; la alternativa descartada era un panel de reproducción.
- [ ] `q.slice(0, 100)` en la búsqueda puede cortar un carácter fuera del plano básico justo en el
  límite (caso muy improbable, mismo tipo que el arreglado en `initials()`).

## Preguntas abiertas

1. **Objetivo ahora**: ¿crecer en tráfico, retener a los usuarios actuales o reforzar la unión
   con gofestivals?
2. ~~Acceso a la base de datos de gofestivals~~ — resuelta: se usa su API pública (ADR 009).
3. ¿Retirar `gofestivals_db_url` de la config del API, que nunca se usó?

## Clasificación automática de emisoras (ADR 012)

**Hecho (2026-11-06/07)**: reglas + segundo clasificador con `claude -p` por suscripción +
evidencia de la web y últimos temas; taxonomía ampliada (subgéneros electrónicos) y navegación por
subgéneros; `enforce` oculta rechazadas y dudosas con tope, marca `hidden_by` y alerta si algo
falla. Cron 05:00 / 05:10 / 05:30 UTC.

- [ ] Tras unos días, revisar `/var/log/radio/classify.log`, el heartbeat y cuántas emisoras
  oculta cada `enforce` (esperable: pocas al día).
- [ ] `noindex` en las fichas de emisoras ocultas (siguen accesibles por URL).
- [ ] Reevaluar las ocultas por duda cuando cambie su web o sus últimos temas (ya entra en la
  huella de evidencia; comprobar que repone alguna).
