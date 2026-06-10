# Sistema de recomendación de emisoras · Documento de diseño

**Fecha:** 2026-06-10 · **Estado:** diseño aprobado, MVP pendiente de implementación
**Stack:** FastAPI + PostgreSQL/PostGIS + Redis + Next.js · 1× Hetzner CX22
**Principio rector:** soluciones pragmáticas que aporten valor rápido antes que ML complejo.
**ADR asociado:** [004-sistema-recomendacion](adr/004-sistema-recomendacion.md)

---

## 1 · Objetivos y métricas

**Objetivo de producto:** que un oyente encuentre su siguiente emisora sin buscar — descubrimiento que retiene, sin burbuja de repetición.

**Limitación clave hoy:** no se captura **duración de escucha** (`station_plays` registra 1 play por identidad/emisora/día UTC, sin stop ni heartbeat) ni se loguean las **búsquedas** (el `q` de `GET /stations` usa pg_trgm y no se persiste). La duración es la señal de calidad por excelencia en radio; su captura está en el roadmap de Fase 2.

**Métricas proxy disponibles ya:**

| Métrica | Fuente | Uso |
|---|---|---|
| Plays diarios por emisora | `station_plays` / `station_plays_daily` | popularidad local |
| Oyentes recurrentes (misma identidad ≥2 días distintos en 7d) | `station_plays` | retención D7 |
| Tasa de favoritos (favoritos / plays únicos) | `user_favorites` | señal explícita fuerte |
| `click_trend` (log-ratio 7d) | cron existente | momentum |

**Captura de duración (Fase 2):** heartbeat `POST /stations/{slug}/heartbeat` cada 60s desde el player (rate-limit con el patrón Redis `INCR+EXPIRE` existente), acumulando `listen_seconds` en `station_plays` con tope diario de 6h. Preferido sobre un evento `stop` con duración calculada en cliente, que se pierde al cerrar la pestaña. Coste: 1 UPDATE/min por oyente activo — trivial para el CX22.

**Targets del sistema (a 3 meses del MVP):**
- CTR del módulo de recomendaciones ≥ 8% (clicks / impresiones).
- Play-through ≥ 60% (click en tarjeta recomendada → `POST /play`).
- Retención D7 de identidades expuestas vs no expuestas: +10% relativo (con la cautela de potencia de §7).
- Cobertura: ≥ 30% del catálogo curated aparece en alguna recomendación semanal (métrica anti-burbuja).

**Relevancia vs exploración:** 10 de 12 slots por score, 2 slots de exploración (~17%, ε-greedy) con emisoras frescas compatibles con el perfil. En fase avanzada, los slots de exploración pasan de ε aleatorio a Thompson Sampling alimentado por `rec_events`.

## 2 · Datos disponibles y estrategia por señal

| Señal | Fuente (ya existe) | Uso |
|---|---|---|
| Historial / frecuencia | `station_plays` (identidad = `COALESCE(user_id, client_id)`, retención 90d) + `station_plays_daily` | semillas del perfil + co-play |
| Favoritos / votos | `user_favorites`, `user_votes` | peso explícito en semillas |
| Géneros | `station_genres(confidence)` sobre el árbol `genres.parent_id` | vector content-based con propagación jerárquica |
| Popularidad global / local | `clickcount`, `votes` (Radio-Browser) / `local_plays_total`, `votes_local` | quality + popularidad local |
| Tendencias | `click_trend` (cron 04:20) + **nuevo** `local_trend` = `ln((plays_7d+1)/(plays_prev_7d+1))` | momentum |
| País / idioma | `country_code`, `language` de la emisora + locale del navegador | cold start + bonus |
| Búsquedas | ❌ no se loguean | gap; opcional Fase 2 (`search_events`) |
| Duración | ❌ no existe | heartbeat en Fase 2 |

### Cold start (usuario sin historial)
- **MVP (coste cero):** `locale` del navegador (`es-ES` → país probable + idioma; el frontend lo pasa explícito como query param para evitar ambigüedad de proxies). Emisoras de ese país/idioma con `quality_score` alto; si no llegan a 12, relleno con el pool *featured* global existente. El usuario nuevo nunca ve el módulo vacío.
- **Fase 2:** GeoIP local con GeoLite2-Country (mmdb ~6 MB en memoria del contenedor API, refresco mensual por cron). País derivado de la IP **sin almacenarla** (bajo riesgo GDPR; documentar en la política de privacidad). Descartados los servicios externos de geo-IP (latencia, dependencia).

### Content-based: vector de géneros con jerarquía
```
w(emisora, género g)  = confidence(g)/100
w(emisora, padre(g)) += 0.5 · confidence(g)/100     (propagación 1 nivel)
```
La propagación hace que tech-house y deep-house se parezcan vía house sin igualarlos. Similitud = coseno entre vectores dispersos (2-5 géneros/emisora). Con miles de emisoras, la matriz completa se computa en segundos en el batch nocturno.

### Colaborativo: co-play desde `station_plays`
Incluye anónimos (identidad = user_id o client_id). Jaccard sobre la ventana de 90 días:
```
J(a,b) = |oyentes(a) ∩ oyentes(b)| / |oyentes(a) ∪ oyentes(b)|       (mínimo 3 co-oyentes)
```
La granularidad 1 play/identidad/día ya viene des-duplicada — ideal para Jaccard. Con base pequeña la matriz es dispersísima: por eso el co-play es **un componente** de la similitud, no el único — degrada con gracia a content-based puro donde no hay datos.

### Contextual (hora del día)
Posponer a Fase 2: con pocos datos el histograma horario por emisora es ruido. Entonces: bonus `+0.05 · afinidad_horaria` (densidad de plays de la emisora en la franja actual, suavizado Laplace) usando el `played_at` ya almacenado.

## 3 · Scoring

### 3.1 Similitud emisora-emisora (precomputada cada noche)
```
sim(a,b) = 0.50·cos_géneros(a,b) + 0.25·jaccard_coplay(a,b)
         + 0.15·[mismo idioma] + 0.10·[mismo país]
```
Se guardan los **top-K=20** vecinos por emisora con `sim ≥ 0.15`, solo destinos `status='active' AND NOT hidden` y `quality_score ≥ 30`. Los componentes se almacenan desglosados (`genre_score`, `coplay_score`) para re-pesar sin recomputar.

### 3.2 Score por usuario (on-the-fly en el request)
Semillas = emisoras con plays 90d + favoritos + votos de la identidad:
```
peso_semilla(s) = plays_90d(s)·exp(-días_desde_último_play/30) + 3·[favorito] + 1·[voto]
```
Candidatos = ∪ top-20 similares de las 10 semillas de mayor peso, excluyendo ya-conocidas (≥3 plays) y favoritos. Score:
```
score(c) = 0.30·max_s[peso_norm(s)·sim(s,c)]    ← afinidad por similitud
         + 0.20·quality_score(c)/100            ← calidad
         + 0.15·afinidad_géneros(perfil, c)     ← coseno perfil vs vector(c), computado on-read
         + 0.10·[idioma del usuario]
         + 0.10·trend_norm(c)                   ← max(click_trend, local_trend) → [0,1]
         + 0.10·pop_local_norm(c)               ← ln(1+plays_30d)/ln(1+max)
         + 0.05·[país del usuario]
```

### 3.3 Re-rank: diversidad + exploración
- **Diversidad:** reutilizar `apply_genre_cap` (`apps/api/app/repos/stations.py`, ya genérico) con cap=3 por género primario para 12 slots, + segunda pasada con cap=6 por país.
- **Exploración (ε-slots):** slots 5 y 10 → emisoras curated con `quality_score ≥ 50`, baja exposición (`plays_30d < p25`) y género compatible con el perfil, al azar ponderado por quality. Alimenta la cobertura y da datos al colaborativo.

### 3.4 Ajuste de pesos
Offline primero (hold-out temporal, §7) comparando configuraciones contra Recall@10; online por interleaving, nunca a ciegas. Los pesos viven en `services/recommendations.py` como constantes documentadas.

## 4 · Arquitectura MVP (2 semanas, sin infra nueva)

**Decisión central — on-the-fly sobre similitud precomputada** (no listas precomputadas por usuario):
- La mayoría de oyentes son `client_id` anónimos, muchos one-shot: precomputar por usuario sería desperdicio.
- El cómputo on-read son 2 queries indexadas (semillas con los índices parciales existentes de `station_plays`; vecinos por PK de `station_similarity`) + blend en Python: <20 ms en el CX22.
- Cache Redis `rec:v1:{identity}` TTL 600s; cold start compartido `rec:v1:cold:{country}:{lang}` TTL 1800s.
- Precompute nocturno para logueados activos: se revisa en Fase 2.

```
                NOCHE (cron secuencial existente)
03:45 retain-plays → 04:00 rb_sync → 04:15 snapshot → 04:20 trends → 04:30 quality
                                                            ↓
                                          04:40 compute-station-similarity (NUEVO)
station_genres ─┐                                           ↓
station_plays ──┼→ coseno géneros + Jaccard co-play ──→ station_similarity (top-20/emisora)
stations ───────┘   + idioma + país

                DÍA (request path)
Next.js (home "Para ti" client-fetch · detalle "Similares" ISR)
   │ GET /stations/recommended?client_id&locale&size=12
   ▼
api/v1 → services/recommendations → Redis rec:v1:{identity} (hit → fin, <2 ms)
              │ miss
              ▼
        repos/recommendations:
          1. semillas: plays 90d + favoritos + votos de la identidad
          2. candidatos: station_similarity de las top-10 semillas
          3. blend §3.2 + apply_genre_cap + ε-slots
          4. cold start si 0 semillas: país/idioma del locale → featured
              ▼
        Redis SET 600s → 12 emisoras
Frontend → POST /recs/events (impresiones batch + clicks) → rec_events → evaluación (§7)
```

**Componentes nuevos:**
- `packages/scripts/scripts/compute_station_similarity.py` + entry en `pyproject.toml` + alta en `_ALLOWED_COMMANDS` (`run_pending_admin_jobs.py`) y `operations_catalog.py` (relanzable desde el panel admin) + cron `40 4 * * *`.
- `apps/api`: `repos/recommendations.py` → `services/recommendations.py` → rutas en `api/v1/stations.py` y `api/v1/recs.py` (capas idiomáticas del repo, SQL crudo con `text()`).
- `apps/web`: módulo "Para ti" en home (client-fetch con el `client_id` de localStorage; no ISR por ser personalizado) y "Emisoras similares" en el detalle (ISR, no personalizado). Reutilizan `StationGrid`/`StationCard`.

**Ventajas:** cero infra nueva, explicable ("porque escuchas X"), barato, degrada con gracia.
**Inconvenientes:** no capta gustos latentes cross-género (mitigado por propagación jerárquica + co-play) ni secuencia/contexto.

## 5 · Fase 2 (2 meses) — evaluación honesta de cada opción

| Opción | Pros | Contras | Veredicto |
|---|---|---|---|
| Item-item CF con time-decay (Jaccard → coseno ponderado por recencia) | Incremental sobre el MVP; robusto con datos escasos; explicable | Sin descubrimiento cross-género profundo | **Hacer** (2-3 días) |
| ALS implícito (`implicit`, factores=32) | Estándar probado; capta gustos latentes; entrenable en segundos a esta escala | **No hay densidad de datos que lo alimente todavía**; anónimos efímeros contaminan; otro artefacto que mantener | **Posponer** — gatillo: >5k identidades con ≥5 emisoras distintas/90d |
| Similitud por artistas de `now_playing` (TF-IDF coseno sobre top-artistas 30d) | Señal única: emisoras que pinchan los mismos artistas se parecen aunque sus tags difieran; sin modelos externos | Metadata ICY ruidosa (normalizar artistas) | **Hacer la variante barata** como 4º componente de `sim(a,b)` (peso 0.15); pgvector innecesario a esta escala |

También en Fase 2: heartbeat de duración (§1), GeoIP local (§2), feature horaria (§2), precompute para logueados activos, interleaving + dashboard de CTR (query sobre `rec_events` en el panel admin existente).

## 6 · Fase avanzada (6 meses)

- **Thompson Sampling en los slots de exploración:** Beta(clicks+1, impresiones−clicks+1) por emisora desde `rec_events`, con país como bucket de contexto. Un sampling por candidato en el request — el paso "avanzado" más rentable y honesto para este VPS.
- **Sequence-aware (SASRec/GRU4Rec): NO recomendado en este horizonte.** Con 1 evento/día/usuario no hay secuencias significativas (radio ≠ scroll de e-commerce), y transformers en 2 vCPU compartidas con API+Postgres+Redis es mala asignación de recursos. Condición de reapertura: eventos de sesión finos (skip/stop/duración) + >50k MAU + worker dedicado.
- Re-evaluar ALS contra el gatillo de §5; retención 90d de `rec_events` (mismo patrón que plays); batch incremental si el catálogo supera ~20k emisoras.

## 7 · Evaluación

**Offline (con datos existentes):**
- Hold-out temporal: similitud entrenada con plays hasta el día D, evaluación con plays D+1..D+7. **Recall@10**: ¿la emisora nueva que escuchó estaba en su top-10? Baselines a batir: popularidad global y por país.
- **Coverage semanal**: % del catálogo curated que aparece en alguna lista.
- Script `eval_recommendations.py` en `packages/scripts` (solo lectura, ad-hoc).

**Online (requiere `rec_events`):** CTR por superficie y slot, play-through (click → play <5 min, join por identidad), D7 de expuestos.

**A/B — honestidad sobre potencia estadística:** asignación determinista `crc32(client_id) % 100` (estable, sin cookies extra, cubre anónimos). Para detectar CTR 5%→6% (α=0.05, potencia 0.8) hacen falta ~8.000 identidades por brazo → un A/B clásico estaría **infrapotenciado durante meses** con la base actual. Por defecto:
1. **Interleaving team-draft** (mezclar rankings A y B en una lista, atribuir clicks por equipo): ~10× menos muestra para comparar rankers.
2. Medir deltas grandes primero (módulo vs no-módulo), no variantes finas.
3. Ventanas de 4-8 semanas y conclusiones direccionales.

## 8 · Escalabilidad

El coste del modelo ítem-ítem escala con el **catálogo** (miles, estable), no con los usuarios.

| Escala | Cuello de botella | Acción |
|---|---|---|
| 10k MAU | Ninguno real | Stack actual tal cual: batch <1 min, `station_plays` ~10⁶ filas/90d con los índices existentes |
| 100k MAU | QPS de `/recommended`, tamaño de plays (~10⁷/90d) | TTLs mayores, precompute del ~10% de identidades activas a Redis, co-play desde agregados+muestreo, upgrade vertical del VPS (CX32/42 — lo barato primero) |
| 1M MAU | Una sola caja deja de ser razonable | Postgres dedicado/gestionado + réplica de lectura para recs, worker de batch propio, pgvector+IVFFlat si el catálogo creció, CDN para cold-start cacheable. **Cambia el despliegue, no el algoritmo** |

## 9 · Roadmap

**Semanas 1-2 — MVP:**
1. Migración alembic 0017: `station_similarity` + `rec_events`.
2. `compute_station_similarity.py` + tests de integración + alta en catálogo de operaciones admin + cron 04:40.
3. `repos/recommendations.py` + `services/recommendations.py` (blend, cache, cold start) + rutas + schemas.
4. Extensión de `apply_genre_cap` con segunda pasada de cap por país.
5. Frontend: "Para ti" (home) + "Similares" (detalle).
6. `eval_recommendations.py` con baseline de popularidad.

**Mes 1-2 — Fase 2:** heartbeat `listen_seconds` · GeoIP GeoLite2 + cron de refresco · time-decay + componente de artistas · interleaving + dashboard CTR en admin · feature horaria · precompute para logueados activos.

**Mes 3-6 — Avanzada:** Thompson Sampling en ε-slots · re-evaluación de ALS por gatillo de datos · retención de `rec_events` · hardening de escala según tracción.

## 10 · DDL y endpoints

```sql
-- 0017_create_recommendation_tables.py
CREATE TABLE station_similarity (
    station_id         UUID NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    similar_station_id UUID NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    score        REAL NOT NULL,            -- blend §3.1, [0,1]
    genre_score  REAL NOT NULL DEFAULT 0,  -- componentes desglosados: re-pesar sin recomputar
    coplay_score REAL NOT NULL DEFAULT 0,
    rank         SMALLINT NOT NULL,        -- 1..20
    computed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_station_similarity PRIMARY KEY (station_id, similar_station_id),
    CONSTRAINT chk_similarity_not_self CHECK (station_id <> similar_station_id),
    CONSTRAINT chk_similarity_score CHECK (score >= 0 AND score <= 1)
);
CREATE INDEX idx_station_similarity_lookup ON station_similarity (station_id, rank);

CREATE TABLE rec_events (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    station_id  UUID NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    client_id   UUID,
    event_type  TEXT NOT NULL,             -- 'impression' | 'click'
    surface     TEXT NOT NULL,             -- 'home_for_you' | 'station_similar'
    variant     TEXT,                      -- bucket A/B o equipo de interleaving
    slot        SMALLINT,                  -- posición (CTR posicional)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_rec_events_identity CHECK ((user_id IS NULL) <> (client_id IS NULL)),
    CONSTRAINT chk_rec_events_type CHECK (event_type IN ('impression','click'))
);
CREATE INDEX idx_rec_events_station_created ON rec_events (station_id, created_at);
CREATE INDEX idx_rec_events_created ON rec_events (created_at);   -- retención 90d

-- Fase 2 (migración aparte):
-- ALTER TABLE station_plays       ADD COLUMN listen_seconds INTEGER NOT NULL DEFAULT 0;
-- ALTER TABLE station_plays_daily ADD COLUMN listen_seconds BIGINT  NOT NULL DEFAULT 0;
```

```
GET  /api/v1/stations/recommended?client_id=<uuid>&locale=es-ES&size=12   → StationsPage
GET  /api/v1/stations/{slug}/similar?size=6                               → list[StationSummary]
POST /api/v1/recs/events   {surface, variant?, events:[{station_id, event_type, slot}]}
POST /api/v1/stations/{slug}/heartbeat   (Fase 2)                         → 204
```

Auth opcional en `/recommended` con el mismo patrón identidad que `POST /{slug}/play` (JWT pisa `client_id`). Frecuencia de actualización: similitud 1×/día (04:40); recs por usuario en cada request con cache 600s; cold start 1800s.

## 11 · Tres perfiles trabajados

**(a) Anónimo nuevo en España.** `client_id` recién minteado, 0 plays → cold start. `locale=es-ES` → país ES, idioma español. Emisoras activas/visibles ES o en español por `quality_score`; solo hay 7 con quality ≥ 50 → se completa con el pool featured global hasta 12. `apply_genre_cap(3)` evita cinco technos seguidas; slots 5 y 10 = curated ES poco expuestas. Cacheado como `rec:v1:cold:ES:spanish` 30 min — todos los nuevos españoles comparten lista (barato y correcto).

**(b) Logueado, 30 plays techno/trance, 5 favoritos.** 8 semillas; la mayor: 14 plays, último hace 2 días, favorita → `peso = 14·exp(-2/30) + 3 ≈ 16.1`. ~90 candidatos tras exclusiones. Ejemplo, emisora hard-trance alemana (quality 78, trend 0.4, sim 0.74 con su mejor semilla):
`score = 0.30·(0.92·0.74) + 0.20·0.78 + 0.15·0.81 + 0.10·0 + 0.10·0.70 + 0.10·0.45 + 0.05·0 = 0.597` → top-3. Los caps fuerzan acid/progressive vía árbol; slot 5 = psytrance poco expuesta (compatible vía padre "trance").

**(c) Anónimo fiel a una emisora de drum&bass (25 plays/90d).** 1 semilla de peso alto → candidatos = sus 20 vecinos: dominan dnb/jungle por coseno y 2-3 emisoras con Jaccard alto (el colaborativo brilla en emisoras populares de la app aunque haya pocos datos globales). La semilla se excluye (≥3 plays). El cap de género (3 dnb) obliga a que entren jungle/breakbeat — hermanos en el árbol: exactamente el ensanchamiento de burbuja buscado. Relleno con cold start de su locale si faltan slots. Riesgo anotado: si pincha una recomendación y vuelve a su emisora, `rec_events` registra click sin retención — señal que el bandit de la fase avanzada aprenderá a descontar.
