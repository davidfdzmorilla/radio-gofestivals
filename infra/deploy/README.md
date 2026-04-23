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
docker compose -f docker-compose.prod.yml --profile cron run --rm scripts \
  rb_sync run --limit 200

docker compose -f docker-compose.prod.yml --profile cron run --rm scripts \
  rb_sync auto-curate-top --limit 50 --admin-email tu@email

# 6. Crontab
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

El script hace backup, build, migraciones, rolling up con healthchecks,
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
docker compose -f docker-compose.prod.yml --profile cron run --rm scripts \
  rb_sync run --limit 500
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

## 6 · Seguridad

- `.env.production` **nunca** va al repo (`.gitignore` lo incluye).
- Rotar `JWT_SECRET` invalida todos los tokens de admin emitidos.
  Tras rotar, hay que hacer login de nuevo en el panel de admin.
- `POSTGRES_PASSWORD` y `REDIS_PASSWORD`: al cambiarlos hay que
  recrear los contenedores para que cojan el nuevo valor.
- No hacer `git push` desde el VPS. El VPS es solo destino de deploy.
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
