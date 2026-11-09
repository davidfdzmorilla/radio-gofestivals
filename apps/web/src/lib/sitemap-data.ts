import {
  isComboIndexable,
  isCountryIndexable,
  isGenreIndexable,
  isStationIndexable,
} from './indexability';
import { TRENDING_GENRE_GATE_MIN, xDefaultUrl } from './seo';

const SITE = 'https://radio.gofestivals.eu';
const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const LOCALES = ['es', 'en'] as const;
// x-default viene de xDefaultUrl (lib/seo.ts), el mismo que declaran las páginas.
const PAGE_SIZE = 50;

export const SITEMAP_REVALIDATE_SECONDS = 86_400;

type Station = {
  slug: string;
  logo_hash?: string | null;
  country_code: string | null;
  genres: string[];
  quality_score: number;
};
type StationPage = { items: Station[]; pages: number };
type Genre = {
  slug: string;
  parent_id: number | null;
  station_count: number;
  children?: Genre[];
};
type CountryFacet = { code: string; station_count: number };

function flattenGenres(tree: Genre[]): Genre[] {
  const out: Genre[] = [];
  for (const g of tree) {
    out.push(g);
    if (g.children?.length) out.push(...flattenGenres(g.children));
  }
  return out;
}

export interface SitemapEntry {
  url: string;
  /**
   * ISO 8601. Hoy NO se rellena: `stations.updated_at` lo reescribe a diario el health-check, así
   * que no es una fecha de cambio real y un lastmod falso hace que Google ignore el de todo el
   * sitio. Se recuperará cuando haya una fecha de cambio de contenido fiable.
   */
  lastModified?: string;
  alternates: Record<string, string>;
}

export type SitemapGroup = 'static' | 'genres' | 'countries' | 'stations';
export type SitemapGroups = Record<SitemapGroup, SitemapEntry[]>;

function localizedEntries(path: string): SitemapEntry[] {
  // Next.js redirige /<locale>/ → /<locale>: las URLs del sitemap deben ser canónicas (200).
  const suffix = path === '/' ? '' : path;
  const alternates: Record<string, string> = Object.fromEntries(
    LOCALES.map((l) => [l, `${SITE}/${l}${suffix}`]),
  );
  alternates['x-default'] = xDefaultUrl(suffix);
  return LOCALES.map((locale) => ({
    url: `${SITE}/${locale}${suffix}`,
    alternates,
  }));
}

async function fetchAllStations(): Promise<Station[]> {
  // Tolerante a API caída (p. ej. `next build` en CI sin backend): el
  // sitemap degrada a rutas estáticas y se rellena al revalidar.
  const first = await fetch(`${API}/api/v1/stations?size=${PAGE_SIZE}&page=1`, {
    next: { revalidate: SITEMAP_REVALIDATE_SECONDS },
  }).catch(() => null);
  if (!first?.ok) return [];
  const firstPage = (await first.json()) as StationPage;
  const out: Station[] = [...firstPage.items];

  const remaining = await Promise.all(
    Array.from({ length: Math.max(0, firstPage.pages - 1) }, (_, i) =>
      fetch(`${API}/api/v1/stations?size=${PAGE_SIZE}&page=${i + 2}`, {
        next: { revalidate: SITEMAP_REVALIDATE_SECONDS },
      })
        .then((r) => (r.ok ? (r.json() as Promise<StationPage>) : null))
        .catch(() => null),
    ),
  );
  for (const page of remaining) if (page) out.push(...page.items);
  return out;
}

async function fetchAllGenres(): Promise<Genre[]> {
  const res = await fetch(`${API}/api/v1/genres`, {
    next: { revalidate: SITEMAP_REVALIDATE_SECONDS },
  }).catch(() => null);
  if (!res?.ok) return [];
  return flattenGenres((await res.json()) as Genre[]);
}

async function fetchCountryFacets(genre?: string): Promise<CountryFacet[]> {
  const qs = genre ? `?genre=${encodeURIComponent(genre)}` : '';
  const res = await fetch(`${API}/api/v1/stations/facets/countries${qs}`, {
    next: { revalidate: SITEMAP_REVALIDATE_SECONDS },
  }).catch(() => null);
  if (!res?.ok) return [];
  return (await res.json()) as CountryFacet[];
}

/**
 * Entradas de sitemap agrupadas por tipo. Solo lo indexable según lib/indexability.ts: el MISMO
 * criterio que el <meta robots> de cada página (lo listado y lo declarado no pueden divergir).
 * Sin `lastmod` (ver `SitemapEntry.lastModified`).
 */
export async function buildSitemapGroups(): Promise<SitemapGroups> {
  const [allStations, allGenres, countries] = await Promise.all([
    fetchAllStations(),
    fetchAllGenres(),
    fetchCountryFacets(),
  ]);

  const stations = allStations.filter((s) =>
    isStationIndexable({ ...s, genreCount: s.genres.length }),
  );
  const genres = allGenres.filter((g) => isGenreIndexable(g.station_count));
  const gatedCountries = countries.filter((c) => isCountryIndexable(c.station_count));
  const trendingGenres = allGenres.filter(
    (g) => g.parent_id === null && g.station_count >= TRENDING_GENRE_GATE_MIN,
  );
  // TODOS los géneros (no solo raíz): los hubs de país enlazan combos de subgéneros.
  const combos = (
    await Promise.all(
      allGenres.map(async (g) => {
        const facets = await fetchCountryFacets(g.slug);
        return facets
          .filter((f) => isComboIndexable(f.station_count))
          .map((f) => ({ code: f.code.toLowerCase(), genre: g.slug }));
      }),
    )
  ).flat();

  return {
    static: [
      ...localizedEntries('/'),
      ...localizedEntries('/genres'),
      ...localizedEntries('/countries'),
      ...localizedEntries('/trending'),
      ...localizedEntries('/for-stations'),
      ...trendingGenres.flatMap((g) =>
        localizedEntries(`/trending/${g.slug}`),
      ),
    ],
    genres: genres.flatMap((g) =>
      localizedEntries(`/genres/${g.slug}`),
    ),
    countries: [
      ...gatedCountries.flatMap((c) => localizedEntries(`/countries/${c.code.toLowerCase()}`)),
      ...combos.flatMap((c) => localizedEntries(`/countries/${c.code}/${c.genre}`)),
    ],
    stations: stations.flatMap((s) =>
      localizedEntries(`/stations/${s.slug}`),
    ),
  };
}

// Los cuatro hijos del índice se piden casi a la vez: una sola construcción compartida y cacheada
// en memoria (la caché HTTP de la respuesta cubre el resto).
const MEMO_TTL_MS = 10 * 60 * 1000;
let memo: { at: number; value: Promise<SitemapGroups> } | null = null;

export function getSitemapGroups(): Promise<SitemapGroups> {
  if (memo && Date.now() - memo.at < MEMO_TTL_MS) return memo.value;
  const value = buildSitemapGroups().catch((err: unknown) => {
    memo = null; // un fallo no se cachea
    throw err;
  });
  memo = { at: Date.now(), value };
  return value;
}

export function resetSitemapMemoForTests(): void {
  memo = null;
}
