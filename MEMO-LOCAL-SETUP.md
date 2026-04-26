## Causa

El volumen Docker `radio_postgres_data` local persiste un password antiguo
(generado en Fase 01). El `.env` local tiene un password distinto.

Compose aplica `POSTGRES_PASSWORD` solo al **inicializar** el volumen, no
en arranques posteriores con volumen ya existente.

## Para arreglar mañana

```bash
# Opción A - reset volumen (datos locales se pierden, no críticos en dev)
docker compose down -v
docker compose up -d postgres redis

# Opción B - actualizar password del rol existente
docker exec -it radio-postgres psql -U radio -d radio
# Y dentro: ALTER USER radio PASSWORD '<password-del-.env>';
```

## Después aplicar migraciones (puerto 5433, no 5432)

```bash
cd apps/api
DATABASE_URL=postgresql+asyncpg://radio:$POSTGRES_PASSWORD@localhost:5433/radio \
  uv run alembic upgrade head
```

## Nota: por qué :5433

`docker-compose.yml` mapea Postgres al :5433 del host porque el :5432 está
ocupado por Postgres de Homebrew en el Mac.
