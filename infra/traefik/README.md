# Traefik labels · radio.gofestivals

Los labels que Traefik lee viven en `docker-compose.prod.yml`, no aquí.
Este archivo documenta la convención.

## Routing

- **Router `radio-api`** · prioridad `10`
  - Regla: `Host(radio.gofestivals.eu) && (PathPrefix(/api) || PathPrefix(/ws))`
  - Apunta al servicio `api:8000`
  - Middleware `radio-api-headers` (HSTS 1 año, X-Content-Type-Options)
- **Router `radio-web`** · prioridad `1` (catch-all del dominio)
  - Regla: `Host(radio.gofestivals.eu)`
  - Apunta al servicio `web:3000`

Traefik evalúa primero el router de prioridad alta, así que `/api/*` y `/ws/*`
llegan al backend Python. Todo lo demás va al Next.js.

## TLS

Certresolver `letsencrypt` (configurado a nivel Traefik del VPS, no aquí).
Entrypoint `websecure` (443). El puerto 80 lo gestiona Traefik con redirect
automático a 443 en su propia config.

## Red

Red externa `traefik_proxy`. El compose prod adjunta `api` y `web` a esa red.
`postgres`, `redis` e `icy-worker` viven SOLO en la red interna
`radio_internal`; no son alcanzables desde fuera del stack.

## Añadir un nuevo dominio / subdominio

1. DNS al VPS.
2. Nuevo router en los labels del servicio pertinente: cambiar la regla
   `Host(...)` o añadir otro `traefik.http.routers.NAME.rule=...`.
3. `docker compose -f docker-compose.prod.yml up -d --force-recreate web`
   (o `api`) para que Traefik recoja los nuevos labels.
