# Runbook · radio.gofestivals (staging/prod)

Despliegue manual en VPS Hetzner compartido con otros proyectos (formate.es,
nyx, …). Traefik con Let's Encrypt ya operativo. Red externa `traefik_proxy`.

## 0 · Primera vez · checklist

- [ ] **Snapshot Hetzner** del VPS tomado (responsabilidad del operador).
- [ ] DNS `radio.gofestivals.eu` apuntando al VPS. Verificar:
  ```
  dig +short radio.gofestivals.eu
  # debe devolver la IP del VPS
  ```
- [ ] Red `traefik_proxy` existe: `docker network ls | grep traefik_proxy`.
- [ ] Usuario del VPS pertenece al grupo `docker`.
- [ ] Directorios para logs y backups:
  ```
  sudo mkdir -p /var/log/radio /var/backups/radio-gofestivals
  sudo chown $(whoami): /var/log/radio /var/backups/radio-gofestivals
  ```
- [ ] Repo clonado en `/home/david/compose/radio-gofestivals`:
  ```
  sudo mkdir -p /home/david/compose/radio-gofestivals
  sudo chown $(whoami): /home/david/compose/radio-gofestivals
  cd /opt && git clone <repo-url> radio-gofestivals
  cd radio-gofestivals
  ```

## 1 · Primer deploy

```bash
cd /home/david/compose/radio-gofestivals

# 1. Crear .env.production con secretos rotados
cp .env.production.example .env.production
# Generar valores y pegarlos:
openssl rand -base64 24   # POSTGRES_PASSWORD
openssl rand -base64 24   # REDIS_PASSWORD
openssl rand -hex 32      # JWT_SECRET
$EDITOR .env.production

# 2. Deploy
./infra/deploy/deploy.sh

# 3. Verificación manual
curl -I https://radio.gofestivals.eu/        # 200 + TLS
curl    https://radio.gofestivals.eu/api/v1/genres | head

# 4. Crear primer admin
docker compose -f docker-compose.prod.yml --profile cron run --rm scripts \
  bootstrap-admin --email tu@email --name "Tu nombre"

# 5. Sync inicial y auto-curación
docker compose --env-file .env.production -f docker-compose.prod.yml \
  --profile cron run --rm scripts rb_sync run --limit 200

docker compose --env-file .env.production -f docker-compose.prod.yml \
  --profile cron run --rm scripts rb_sync auto-curate-top --limit 50 \
  --admin-email tu@email

# 6. Primer cálculo de similitud (recomendaciones); después lo mantiene
#    el cron nocturno de las 04:40
docker compose --env-file .env.production -f docker-compose.prod.yml \
  --profile cron run --rm scripts compute-station-similarity

# 7. Crontab
crontab -e
# pegar contenido de infra/deploy/crontab.example
```

## 2 · Deploy incremental

```bash
ssh vps
cd /home/david/compose/radio-gofestivals
git pull
./infra/deploy/deploy.sh
```

El script hace backup, build de TODAS las imágenes (incluida `scripts`,
gateada por el profile `cron`), migraciones, rolling up con healthchecks,
smoke tests contra el dominio, y rollback automático si algo falla.

Variables útiles:
- `FORCE=1` permite deploy con tree sucio (uso excepcional)
- `SKIP_DNS=1` salta la verificación DNS (útil la primera vez si aún
  no ha propagado)
- `SKIP_SMOKE=1` no recomendado salvo mantenimiento planificado

## 3 · Rollback manual

El deploy.sh lo invoca automáticamente en caso de fallo. Manual:

```bash
# Listar backups disponibles
ls -lh /var/backups/radio-gofestivals/

# Rollback a un backup concreto
./infra/deploy/rollback.sh /var/backups/radio-gofestivals/radio_YYYYMMDDThhmmssZ.sql.gz
```

Si quieres volver al SHA anterior antes del rollback:
```bash
git log --oneline -5
git checkout <sha-anterior>
./infra/deploy/deploy.sh FORCE=1
```

## 4 · Comandos operativos

```bash
# Estado
docker compose -f docker-compose.prod.yml ps

# Logs
docker compose -f docker-compose.prod.yml logs --tail=200 api
docker compose -f docker-compose.prod.yml logs --tail=200 web
docker compose -f docker-compose.prod.yml logs --tail=200 icy-worker

# Reiniciar un servicio
docker compose -f docker-compose.prod.yml restart api

# Entrar en la DB
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U radio -d radio

# Abrir shell en el API (debug)
docker compose -f docker-compose.prod.yml exec api bash

# Backup manual ad-hoc
./infra/deploy/backup-postgres.sh

# Sync Radio-Browser ad-hoc
docker compose --env-file .env.production -f docker-compose.prod.yml \
  --profile cron run --rm scripts rb_sync run --limit 500

# Recalcular similitud de emisoras (recomendaciones) ad-hoc
docker compose --env-file .env.production -f docker-compose.prod.yml \
  --profile cron run --rm scripts compute-station-similarity

# Evaluación offline del recomendador (solo lectura, salida JSON)
docker compose --env-file .env.production -f docker-compose.prod.yml \
  --profile cron run --rm scripts eval-recommendations
```

## 4b · Rotación de logs

Los logs de `/var/log/radio` se rotan con `infra/deploy/logrotate-radio.conf` (diaria,
14 copias comprimidas, `maxsize 50M`, `copytruncate`). Corre desde el crontab de `david`
(no hace falta root; los logs y el directorio son suyos):

```cron
10 2 * * * /usr/sbin/logrotate -s /home/david/.local/state/radio-logrotate.status /home/david/compose/radio-gofestivals/infra/deploy/logrotate-radio.conf >> /var/log/radio/cleanup.log 2>&1
```

El `find -mtime +14 -delete` anterior nunca borraba los logs activos (su mtime se renueva
con cada escritura): `health.log` llegó a 234 MB y `admin-jobs.log` a 97 MB.

## 4c · Imágenes viejas y espacio en disco

Cada deploy construye `api`, `web`, `icy-worker` y `scripts` con el tag del SHA de git. `docker image
prune` solo borra las huérfanas, así que los tags viejos se acumulaban (60 tras ~15 deploys).
`deploy.sh` ejecuta ahora `prune-images.sh` al terminar: conserva las últimas 3 versiones por servicio
(`KEEP_IMAGES`, por defecto 3) y borra el resto. Solo toca tags tipo SHA de `radio-gofestivals/*`: nunca
`latest` ni otros proyectos, y docker se niega a borrar una imagen en uso. El rollback automático usa
IDs de imagen y no depende de esos tags.

**No es la solución a un disco lleno.** Medido el 2026-11-05 (disco al 89 %, 9 GB libres): las
versiones comparten casi todas sus capas, así que borrar 48 tags liberó menos de 0,1 GB. Lo de la
radio es pequeño: imágenes ~1 GB únicos, base de datos 187 MB, backups 232 MB, logs 54 MB. El grueso del
VPS compartido son imágenes de otros proyectos (`wedding-page-frontend` 1,9 GB, `docker-kaleido-web`
1,8 GB…) y 3,9 GB de volúmenes sin usar. La caché de build (6,7 GB) no se puede podar: sus entradas
están en uso por imágenes existentes.

```bash
infra/deploy/prune-images.sh --dry-run   # qué borraría
infra/deploy/prune-images.sh             # borrar de verdad
bash infra/deploy/tests/prune-images.test.sh   # pruebas con un docker simulado
docker system df                         # qué ocupa Docker en el VPS (todos los proyectos)
```

## 5 · Troubleshooting

### 502 Bad Gateway

`api` o `web` no responde. Revisar:
```
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=100 api
```

### 503 Service Unavailable

El contenedor no está adjunto a `traefik_proxy`. Verificar:
```
docker network inspect traefik_proxy | jq '.[] | .Containers | keys'
```

### TLS no activo

Rate limit de Let's Encrypt. Revisar logs de Traefik:
```
docker logs traefik 2>&1 | grep -i 'radio.gofestivals'
```

### DB connectivity desde API

```
docker compose -f docker-compose.prod.yml exec api \
  python -c "from app.core.config import get_settings; print(get_settings().database_url)"
```

### Worker ICY no recibe subscribe

```
docker compose -f docker-compose.prod.yml logs --tail=50 icy-worker
docker compose -f docker-compose.prod.yml exec redis \
  redis-cli -a "$REDIS_PASSWORD" PUBSUB CHANNELS 'icy:*'
```

## 5b · Alerting por Telegram

Diseño y umbrales en `docs/adr/006-alerting-telegram.md`.

**Alta (una vez)**
1. En Telegram, `@BotFather` → `/newbot` → guardar el token. Bot propio de radio, no el del
   monitor de Elasticsearch.
2. Crear un chat o canal para las alertas, añadir el bot y obtener su `chat_id`
   (enviar un mensaje y mirar `https://api.telegram.org/bot<TOKEN>/getUpdates`).
3. Añadir a `.env.production`: `TELEGRAM_ALERT_TOKEN=...` y `TELEGRAM_ALERT_CHAT_ID=...`.
4. Desplegar (el servicio `scripts` ahora depende de redis) y probar:
   ```
   docker compose --env-file .env.production -f docker-compose.prod.yml \
     run --rm -T scripts watchdog notify --key test --message "prueba de alertas"
   ```
5. Instalar las líneas `watchdog` y `summary` de `crontab.example`.

**Qué avisa**: health-check abortado (breaker), caída del catálogo (<80% de la mediana de 7 días),
health-check parado (>13 h), contenedor caído/unhealthy o en bucle de reinicios, `rb_sync` fallido,
jobs envueltos con `run-job.sh` que salen con código != 0, y un resumen diario.

**Silenciar/reiniciar el estado de una alerta**: claves `alert:active:*` y `alert:cd:*` en redis
(`docker exec radio-redis-prod redis-cli --scan --pattern 'alert:*'`).

## 6 · Seguridad

- `.env.production` **nunca** va al repo (`.gitignore` lo incluye).
- Rotar `JWT_SECRET` invalida todos los tokens de admin emitidos.
  Tras rotar, hay que hacer login de nuevo en el panel de admin.
- `POSTGRES_PASSWORD` y `REDIS_PASSWORD`: al cambiarlos hay que
  recrear los contenedores para que cojan el nuevo valor.
- `git push` desde el VPS está autorizado vía deploy key específica del
  repo (`~/.ssh/github_radio`, host `github-radio`), revocable desde
  GitHub → Settings → Deploy keys. Ver CLAUDE.md §11.
- Si al resolver un incidente necesitas ver un log que podría tener
  secretos, filtra con `grep -v` o enmascara antes de compartir.

## 7 · Notas sobre el VPS compartido

El VPS tiene otros proyectos (formate.es, nyx, ...). Operaciones que
afectan **sólo a radio.gofestivals**:

- `docker compose -f docker-compose.prod.yml <cmd>` con el archivo prod.
- Borrar volúmenes `radio_postgres_data` y `radio_redis_data`.
- Borrar imágenes con label `org.opencontainers.image.source=https://github.com/gofestivals/radio`.

**No tocar** la red `traefik_proxy` ni el servicio `traefik` del host —
son compartidos. No hacer `docker system prune -a` sin cuidado.

## 4d · Clasificación automática de emisoras (ADR 012)

Dos jobs diarios (ver `crontab.example`): reglas (`classify-stations run`, 05:00 UTC) y segundo
clasificador (`classify-llm.sh`, 05:10 UTC). Fase 2: solo registran veredicto, no ocultan nada.

- Requiere `claude` instalado y con sesión de suscripción iniciada para el usuario del cron
  (`claude` interactivo una vez; para un servidor sin navegador, `claude setup-token` y
  `CLAUDE_CODE_OAUTH_TOKEN` en el entorno del cron). No debe haber `ANTHROPIC_API_KEY`.
- Cada emisora se juzga con su web (título, descripción) y sus últimos temas cuando los hay.
  Las descargas pasan por el guard SSRF; una web caída no falla la ejecución.
- Ensayo sin escribir: `CLASSIFY_LLM_DRY_RUN=1 infra/deploy/classify-llm.sh`.
- Salida 3 = algún lote falló (límite de uso o sesión caducada); salida 1 = fallo previo (sin
  `claude`, exportación, guardado). En ambos casos `run-job.sh` avisa por Telegram **con la
  causa** («límite de uso de la suscripción», «sesión de Claude caducada: ejecuta `claude` y
  /login…», «claude no respondió en N s», o un extracto literal del error). Se reintenta solo en la
  siguiente ejecución.
- Al volver a funcionar manda un mensaje de recuperación (`watchdog resolve`).
- Latido: al terminar bien toca `/var/log/radio/classify-llm.last-ok`; `watchdog.sh` (cada
  15 min) avisa si lleva más de 36 h sin tocarse (`classify-llm-stale`), p. ej. si el cron deja de
  ejecutarse. Si el fichero no existe (nunca ha corrido bien) no avisa. Ajustable con
  `CLASSIFY_LLM_STALE_HOURS`.
- Pruebas: `bash infra/deploy/tests/classify-llm.test.sh` y `alerting-scripts.test.sh`.
- Ver el resultado: `classify-stations export` (JSON por emisora) o el log
  `/var/log/radio/classify.log`.

### Fase 3a · aplicar el veredicto (`classify-enforce.sh`, 05:30 UTC)

Oculta (`hidden = true`, `hidden_by = 'classifier'`) las emisoras `rejected` y repone las que se
reclasifican. Reutiliza el `hidden` que ya respetan todas las consultas; no cambia ninguna.

- No toca lo oculto por otra vía (spam, manual: `hidden_by` NULL) ni las decisiones `manual`.
- Veredictos de menos de 24 h esperan (`--min-age-hours`). Una **curada** solo se oculta si la
  rechazó el segundo clasificador (que vio su web y temas), nunca solo por reglas.
- **Tope**: si una ejecución quiere ocultar más del 5 % del catálogo visible (mínimo 10) no aplica
  nada, sale con 4 y avisa por Telegram con el motivo.
- Primer despliegue (hay unas 250 rechazadas de golpe): ensayo con
  `infra/deploy/classify-enforce.sh --dry-run --max-change-pct 25`, y si cuadra, sin `--dry-run`.
- Deshacer: `UPDATE stations SET hidden = false, hidden_by = NULL WHERE hidden_by = 'classifier'`
  (y pasar las afectadas a `class_source = 'manual'` si no deben volver a ocultarse).
- Pruebas: `bash infra/deploy/tests/classify-enforce.test.sh`.
