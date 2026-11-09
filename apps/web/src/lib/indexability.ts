import type { Metadata } from 'next';
import { COMBO_GATE_MIN_STATIONS } from './seo';

/**
 * Criterio ÚNICO de indexabilidad (ADR 015). Lo usan tanto `<meta name="robots">` de cada página
 * como los sitemaps: así lo que declara una página y lo que se lista nunca divergen.
 *
 * Datos de partida (9 nov 2026): GSC marcaba 3.660 URLs como "rastreada, sin indexar", casi todas
 * listados finos. Se indexa menos pero mejor; las páginas descartadas siguen existiendo y
 * siguen pasando autoridad (`noindex, follow`).
 */

/** Género: por debajo, listado demasiado fino (hoy 33 de 36 géneros pasan). */
export const GENRE_INDEX_MIN_STATIONS = 8;
/** País: ≥ 5 indexable; 3–4 existe pero `noindex, follow`; < 3 es 404 (COUNTRY_GATE_MIN_STATIONS). */
export const COUNTRY_INDEX_MIN_STATIONS = 5;
/** País × género: misma cifra que su puerta de existencia (por debajo es 404, no noindex). */
export const COMBO_INDEX_MIN_STATIONS = COMBO_GATE_MIN_STATIONS;
/** Emisora: calidad mínima (402 de 1.226 emisoras visibles pasan con logo+género+país). */
export const STATION_INDEX_MIN_QUALITY = 50;

/**
 * Emisoras que Google ya muestra con impresiones o clics en Search Console (9 nov 2026).
 * Se saltan los requisitos de calidad y de logo para no perder esa visibilidad, pero NUNCA la
 * condición `hidden`: si el clasificador la ha ocultado, sigue `noindex`.
 * Revisar cada pocos meses con el informe de rendimiento de GSC.
 */
export const STATION_INDEX_ALLOWLIST: ReadonlySet<string> = new Set([
  'radio-medved',
  'studio-92-92-5-fm-lima',
  'radio-onimai',
  'hardbestfm',
]);

export const NOINDEX_FOLLOW: NonNullable<Metadata['robots']> = { index: false, follow: true };

/** `undefined` (sin directiva, indexable por defecto) o `noindex, follow`. */
export function robotsFor(indexable: boolean): Metadata['robots'] | undefined {
  return indexable ? undefined : NOINDEX_FOLLOW;
}

export const isGenreIndexable = (stationCount: number): boolean =>
  stationCount >= GENRE_INDEX_MIN_STATIONS;

export const isCountryIndexable = (stationCount: number): boolean =>
  stationCount >= COUNTRY_INDEX_MIN_STATIONS;

export const isComboIndexable = (stationCount: number): boolean =>
  stationCount >= COMBO_INDEX_MIN_STATIONS;

export interface StationIndexInput {
  slug: string;
  /** Lista pública: omitido (las ocultas no salen en listados). Ficha: viene de la API. */
  hidden?: boolean;
  logo_hash?: string | null;
  country_code: string | null;
  genreCount: number;
  quality_score: number;
}

export function isStationIndexable(s: StationIndexInput): boolean {
  if (s.hidden) return false;
  if (STATION_INDEX_ALLOWLIST.has(s.slug)) return true;
  return (
    Boolean(s.logo_hash) &&
    Boolean(s.country_code) &&
    s.genreCount > 0 &&
    s.quality_score >= STATION_INDEX_MIN_QUALITY
  );
}

/**
 * Robots de la ficha. Oculta (clasificador/spam) → `noindex, nofollow` como hasta ahora;
 * visible pero floja → `noindex, follow`; el resto, sin directiva.
 */
export function stationRobotsFor(s: StationIndexInput): Metadata['robots'] | undefined {
  if (s.hidden) return { index: false, follow: false };
  return robotsFor(isStationIndexable(s));
}
