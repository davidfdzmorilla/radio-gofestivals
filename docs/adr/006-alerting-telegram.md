# ADR 006 · Alerting por Telegram

## Contexto

El incidente del 2026-10-01 (ver ADR 005) pasó 18 h sin que nadie lo viera: el catálogo público
cayó de ~1500 a 71 estaciones activas y se detectó por casualidad. A la vez, `radio-icy-worker-prod`
llevaba más de 139 000 reinicios por un bug con redis-py 8 sin que nada avisara. Hoy toda la
observabilidad es leer logs a mano.

Necesitamos avisos activos pero con poco ruido. El VPS es compartido y ya hay un bot de Telegram
para otro proyecto (monitor de Elasticsearch); no se reutiliza para no mezclar canales ni
credenciales. Prometheus/Alertmanager (carpeta `infra/prometheus`, vacía) es demasiado para los
cinco contenedores y los pocos jobs de este proyecto.

## Decisión

Módulo `scripts/alerting.py` (httpx contra `sendMessage` de la Bot API, sin dependencias de Telegram)
con dedup en Redis: por clave, un cooldown de 6 h evita repetir la alerta de una caída larga y una
marca `active` permite enviar el mensaje de recuperación al resolverse. Si Redis no responde se envía
sin dedup: preferimos un aviso repetido a perderlo.

Fuentes de alerta: (1) health-check abortado por el breaker y `rb_sync` con ≥3 tags fallidos o nada
descargado, desde los propios jobs; (2) comando `watchdog check` cada 15 min: estaciones activas por
debajo del 80% de la mediana de 7 días (la muestra del día no se aprende si hay alerta), health-check
sin ejecutarse en 13 h, y contenedores caídos, `unhealthy` o con ≥3 reinicios desde la última
comprobación; (3) `infra/deploy/run-job.sh` para jobs de cron con código de salida distinto de 0;
(4) `watchdog summary` diario, que actúa también de latido. El estado de contenedores lo recoge el
host (`watchdog.sh`, `docker inspect`) porque el contenedor `scripts` no tiene socket de Docker, y
se pasa por stdin.

Los comandos `watchdog` exigen `TELEGRAM_ALERT_TOKEN` y `TELEGRAM_ALERT_CHAT_ID` (fallan al
arrancar). Las llamadas embebidas en otros jobs son best-effort y nunca rompen el job. El token va
en la URL de la API, así que se filtra de los logs de httpx.

## Consecuencias

- Positivas: el siguiente incidente de este tipo avisa en minutos; sin servicios nuevos que operar;
  mensajes de recuperación y resumen diario.
- Positivas: la lógica (umbrales, evaluación de contenedores) son funciones puras con tests.
- Negativas: depende de Telegram y de que cron funcione. Si cae el cron o el VPS no avisa nada;
  un heartbeat externo (healthchecks.io o similar) queda pendiente de decisión.
- Negativas: el servicio `scripts` pasa a depender de redis (healthy) en compose.
- Negativas: la caída de catálogo necesita ≥1 día de historial en Redis para tener baseline, y si se
  pierde Redis se reinicia el baseline. Los jobs de cron no tienen mensaje de recuperación (solo cooldown).
- Los umbrales (80%, 13 h, 3 reinicios) son estimaciones sobre la línea base actual; ajustar con datos.
