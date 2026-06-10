-- =============================================================================
-- Seed mínimo para los E2E (idempotente — ON CONFLICT DO NOTHING)
-- =============================================================================
-- Los specs de Playwright necesitan catálogo: emisoras curadas activas con
-- género, stream y similitud para que featured, «Para ti» y «Emisoras
-- similares» rendericen. Los géneros vienen del seed de la migración 0001.

INSERT INTO stations (slug, name, country_code, language, quality_score, status, curated)
VALUES
    ('e2e-techno-uno',  'E2E Techno Uno',  'ES', 'spanish', 85, 'active', true),
    ('e2e-techno-dos',  'E2E Techno Dos',  'ES', 'spanish', 80, 'active', true),
    ('e2e-house-uno',   'E2E House Uno',   'ES', 'spanish', 78, 'active', true),
    ('e2e-house-dos',   'E2E House Dos',   'DE', 'german',  75, 'active', true),
    ('e2e-trance-uno',  'E2E Trance Uno',  'ES', 'spanish', 82, 'active', true),
    ('e2e-ambient-uno', 'E2E Ambient Uno', 'FR', 'french',  70, 'active', true)
ON CONFLICT (slug) DO NOTHING;

INSERT INTO station_genres (station_id, genre_id, source, confidence)
SELECT s.id, g.id, 'manual', 100
FROM stations s
JOIN genres g ON g.slug = CASE
    WHEN s.slug LIKE 'e2e-techno%'  THEN 'techno'
    WHEN s.slug LIKE 'e2e-house%'   THEN 'house'
    WHEN s.slug LIKE 'e2e-trance%'  THEN 'trance'
    WHEN s.slug LIKE 'e2e-ambient%' THEN 'ambient'
END
WHERE s.slug LIKE 'e2e-%'
ON CONFLICT DO NOTHING;

INSERT INTO station_streams (station_id, stream_url, codec, bitrate, is_primary, status)
SELECT s.id, 'https://e2e.invalid/' || s.slug || '.mp3', 'mp3', 192, true, 'active'
FROM stations s
WHERE s.slug LIKE 'e2e-%'
  AND NOT EXISTS (
      SELECT 1 FROM station_streams ss WHERE ss.station_id = s.id
  );

-- Similitud mínima: cada e2e-* tiene como vecinas al resto (rank por quality)
INSERT INTO station_similarity (station_id, similar_station_id, score, rank)
SELECT a.id, b.id, 0.5,
       ROW_NUMBER() OVER (PARTITION BY a.id ORDER BY b.quality_score DESC)
FROM stations a
JOIN stations b ON b.id <> a.id AND b.slug LIKE 'e2e-%'
WHERE a.slug LIKE 'e2e-%'
ON CONFLICT DO NOTHING;
