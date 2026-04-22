-- =============================================================================
-- radio.gofestivals · schema inicial
-- =============================================================================
-- Este schema es la fuente de verdad de la estructura de DB. Lo ejecuta
-- alembic como migración 0001. Para cambios posteriores: nuevas migraciones,
-- nunca editar este archivo retroactivamente.
--
-- Orden de aplicación:
--   1. Extensiones
--   2. Tipos enum
--   3. Tablas (en orden de dependencias)
--   4. Índices
--   5. Seed mínimo (géneros base)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1 · EXTENSIONES
-- -----------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS postgis;     -- coordenadas y distancia
CREATE EXTENSION IF NOT EXISTS "uuid-ossp"; -- uuid_generate_v4
CREATE EXTENSION IF NOT EXISTS pg_trgm;     -- búsqueda fuzzy por nombre


-- -----------------------------------------------------------------------------
-- 2 · TIPOS ENUM
-- -----------------------------------------------------------------------------

CREATE TYPE station_status AS ENUM (
    'pending',     -- recién descubierta, no revisada
    'active',      -- funciona y está curada/aprobada
    'broken',      -- ha fallado health-check repetidas veces
    'rejected',    -- descartada editorialmente
    'unsupported'  -- formato no soportado (p.ej. HLS en fase 1)
);

CREATE TYPE festival_link_type AS ENUM (
    'official',    -- radio oficial del festival
    'city',        -- radio de la ciudad donde se celebra
    'lineup'       -- radio que pincha al lineup
);

CREATE TYPE curation_decision AS ENUM (
    'approve',
    'reject',
    'reclassify'
);


-- -----------------------------------------------------------------------------
-- 3 · TABLAS
-- -----------------------------------------------------------------------------

-- 3.1 · GENRES (taxonomía propia, seedeada manualmente)
CREATE TABLE genres (
    id          smallserial PRIMARY KEY,
    slug        text UNIQUE NOT NULL,
    name        text NOT NULL,
    parent_id   smallint REFERENCES genres(id) ON DELETE SET NULL,
    color_hex   char(7) NOT NULL DEFAULT '#8B4EE8',
    sort_order  smallint NOT NULL DEFAULT 100,
    description text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

-- 3.2 · STATIONS (estaciones de radio)
CREATE TABLE stations (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    rb_uuid         uuid UNIQUE,                    -- stationuuid de Radio-Browser
    slug            text UNIQUE NOT NULL,
    name            text NOT NULL,
    stream_url      text NOT NULL,
    homepage_url    text,
    country_code    char(2),                        -- ISO 3166-1 alpha-2
    city            text,
    geo             geography(POINT, 4326),         -- lng/lat en grados
    codec           text,                           -- mp3, aac, opus
    bitrate         int,                            -- kbps
    language        text,
    curated         bool NOT NULL DEFAULT false,    -- aprobada editorialmente
    quality_score   smallint NOT NULL DEFAULT 50,   -- 0-100
    status          station_status NOT NULL DEFAULT 'pending',
    failed_checks   smallint NOT NULL DEFAULT 0,
    last_check_ok   timestamptz,
    last_sync_at    timestamptz,
    source          text NOT NULL DEFAULT 'radio-browser', -- 'radio-browser' | 'manual'
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_quality_score CHECK (quality_score BETWEEN 0 AND 100),
    CONSTRAINT chk_bitrate CHECK (bitrate IS NULL OR bitrate > 0)
);

-- 3.3 · STATION_GENRES (N:M stations ↔ genres)
CREATE TABLE station_genres (
    station_id  uuid REFERENCES stations(id) ON DELETE CASCADE,
    genre_id    smallint REFERENCES genres(id) ON DELETE CASCADE,
    confidence  smallint NOT NULL DEFAULT 50,         -- 0-100, útil para revisión
    source      text NOT NULL,                        -- 'rb_tag' | 'manual' | 'inferred'
    created_at  timestamptz NOT NULL DEFAULT now(),

    PRIMARY KEY (station_id, genre_id),
    CONSTRAINT chk_sg_confidence CHECK (confidence BETWEEN 0 AND 100)
);

-- 3.4 · NOW_PLAYING (historial circular de canciones)
CREATE TABLE now_playing (
    id           bigserial PRIMARY KEY,
    station_id   uuid NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    title        text,
    artist       text,
    raw_metadata text,                               -- StreamTitle crudo por si parseo falla
    captured_at  timestamptz NOT NULL DEFAULT now()
);

-- 3.5 · FESTIVAL_STATIONS (vínculo con gofestivals existente)
-- NOTA: festival_id apunta a la DB de gofestivals (cross-database logical ref).
-- No FK porque vive en otra DB (WordPress/MySQL). Integridad se valida en app layer.
CREATE TABLE festival_stations (
    festival_id  bigint NOT NULL,                    -- id del festival en gofestivals
    station_id   uuid NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    link_type    festival_link_type NOT NULL,
    priority     smallint NOT NULL DEFAULT 50,       -- orden de exhibición
    notes        text,                               -- por qué se vincularon
    created_at   timestamptz NOT NULL DEFAULT now(),

    PRIMARY KEY (festival_id, station_id)
);

-- 3.6 · ADMINS (single-user bootstrap, escalable si hay equipo)
CREATE TABLE admins (
    id             uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    email          text UNIQUE NOT NULL,
    password_hash  text NOT NULL,                    -- bcrypt o argon2
    name           text,
    active         bool NOT NULL DEFAULT true,
    last_login_at  timestamptz,
    created_at     timestamptz NOT NULL DEFAULT now()
);

-- 3.7 · CURATION_LOG (auditoría de decisiones editoriales)
CREATE TABLE curation_log (
    id          bigserial PRIMARY KEY,
    admin_id    uuid NOT NULL REFERENCES admins(id),
    station_id  uuid NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    decision    curation_decision NOT NULL,
    notes       text,
    created_at  timestamptz NOT NULL DEFAULT now()
);


-- -----------------------------------------------------------------------------
-- 4 · ÍNDICES
-- -----------------------------------------------------------------------------

-- Stations: los queries más comunes son por status + curated, por país, por
-- proximidad geográfica, y búsqueda fuzzy por nombre.
CREATE INDEX idx_stations_status         ON stations(status);
CREATE INDEX idx_stations_curated_status ON stations(curated, status)
    WHERE status = 'active';                         -- partial index: mucho más pequeño
CREATE INDEX idx_stations_country        ON stations(country_code)
    WHERE status = 'active';
CREATE INDEX idx_stations_geo            ON stations USING gist(geo);
CREATE INDEX idx_stations_name_trgm      ON stations USING gin(name gin_trgm_ops);
CREATE INDEX idx_stations_rb_uuid        ON stations(rb_uuid)
    WHERE rb_uuid IS NOT NULL;

-- Station_genres: queries típicas son "todas las stations de este género"
CREATE INDEX idx_station_genres_genre    ON station_genres(genre_id);

-- Now_playing: queries son por station_id ORDER BY captured_at DESC.
-- Este índice es crítico porque esta tabla crece rápido.
CREATE INDEX idx_now_playing_station_time
    ON now_playing(station_id, captured_at DESC);

-- Festival_stations
CREATE INDEX idx_festival_stations_station ON festival_stations(station_id);

-- Curation_log
CREATE INDEX idx_curation_log_station ON curation_log(station_id, created_at DESC);
CREATE INDEX idx_curation_log_admin   ON curation_log(admin_id, created_at DESC);


-- -----------------------------------------------------------------------------
-- 5 · TRIGGERS (updated_at automático)
-- -----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_stations_updated_at
    BEFORE UPDATE ON stations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_genres_updated_at
    BEFORE UPDATE ON genres
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- -----------------------------------------------------------------------------
-- 6 · SEED DE GÉNEROS (taxonomía base electrónica)
-- -----------------------------------------------------------------------------
-- Árbol jerárquico. Los géneros raíz tienen parent_id NULL.
-- Los colores siguen la paleta del brand (púrpura + variantes).

INSERT INTO genres (slug, name, parent_id, color_hex, sort_order) VALUES
    -- Raíces
    ('techno',     'Techno',      NULL, '#8B4EE8', 10),
    ('house',      'House',       NULL, '#E62DE9', 20),
    ('trance',     'Trance',      NULL, '#1CC1F9', 30),
    ('dnb',        'Drum & Bass', NULL, '#A61AA9', 40),
    ('dubstep',    'Dubstep',     NULL, '#5F2FA8', 50),
    ('ambient',    'Ambient',     NULL, '#15A8DA', 60),
    ('hardstyle',  'Hardstyle',   NULL, '#C424C7', 70),
    ('breakbeat',  'Breakbeat',   NULL, '#8B4EE8', 80),
    ('electronic', 'Electronic',  NULL, '#8B4EE8', 90); -- catch-all

-- Subgéneros (referencia al parent por slug sería mejor pero es seed inicial)
INSERT INTO genres (slug, name, parent_id, color_hex, sort_order)
SELECT 'deep-house', 'Deep House', id, '#E62DE9', 21 FROM genres WHERE slug = 'house'
UNION ALL
SELECT 'tech-house', 'Tech House', id, '#E62DE9', 22 FROM genres WHERE slug = 'house'
UNION ALL
SELECT 'progressive', 'Progressive', id, '#1CC1F9', 31 FROM genres WHERE slug = 'trance'
UNION ALL
SELECT 'minimal', 'Minimal Techno', id, '#8B4EE8', 11 FROM genres WHERE slug = 'techno'
UNION ALL
SELECT 'liquid-dnb', 'Liquid D&B', id, '#A61AA9', 41 FROM genres WHERE slug = 'dnb';
