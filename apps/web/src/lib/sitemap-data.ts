import type { MetadataRoute } from 'next';
import {
  COMBO_GATE_MIN_STATIONS,
  COUNTRY_GATE_MIN_STATIONS,
  TRENDING_GENRE_GATE_MIN,
} from './seo';

const SITE = 'https://radio.gofestivals.eu';
const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const LOCALES = ['es', 'en'] as const;
// Debe coincidir con X_DEFAULT_LOCALE de lib/seo.ts: si el sitemap y las
// páginas declaran x-default distintos, Google recibe hreflang contradictorio.
const X_DEFAULT_LOCALE: (typeof LOCALES)[number] = 'en';
const PAGE_SIZE = 50;

export const SITEMAP_REVALIDATE_SECONDS = 86_400;

type Station = { slug: string; updated_at?: string | null };
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

function localizedEntries(
  path: string,
  changeFrequency?: MetadataRoute.Sitemap[number]['changeFrequency'],
  priority?: number,
  lastModified?: string,
): MetadataRoute.Sitemap {
  // Next.js redirects /<locale>/ → /<locale> (308). Sitemap URLs must be
  // canonical (200 OK), so drop the trailing slash for the home path.
  const suffix = path === '/' ? '' : path;
  const languages: Record<string, string> = Object.fromEntries(
    LOCALES.map((l) => [l, `${SITE}/${l}${suffix}`]),
  );
  languages['x-default'] = `${SITE}/${X_DEFAULT_LOCALE}${suffix}`;
  return LOCALES.map((locale) => ({
    url: `${SITE}/${locale}${suffix}`,
    changeFrequency,
    priority,
    ...(lastModified ? { lastModified } : {}),
    alternates: { languages },
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
 * Builds the full set of sitemap entries (static pages + every genre, gated
 * country, ranking and station, each localized with hreflang alternates).
 * Shared by the native `app/sitemap.ts` and the `app/sitemap-v2.xml` Route
 * Handler so the two never drift. The country and trending gates use the
 * SAME thresholds as the pages (lib/seo.ts) so a URL is never listed
 * without existing nor vice versa.
 */
export async function buildSitemapEntries(): Promise<MetadataRoute.Sitemap> {
  const [stations, genres, countries] = await Promise.all([
    fetchAllStations(),
    fetchAllGenres(),
    fetchCountryFacets(),
  ]);

  const gatedCountries = countries.filter(
    (c) => c.station_count >= COUNTRY_GATE_MIN_STATIONS,
  );
  const trendingGenres = genres.filter(
    (g) => g.parent_id === null && g.station_count >= TRENDING_GENRE_GATE_MIN,
  );
  // Combos país×género: misma fuente y gate que la página y los hubs.
  // TODOS los géneros (no solo raíz): los hubs de país enlazan combos de
  // subgéneros (p. ej. deep-house) y lo enlazado debe estar en el sitemap.
  const combos = (
    await Promise.all(
      genres.map(async (g) => {
        const facets = await fetchCountryFacets(g.slug);
        return facets
          .filter((f) => f.station_count >= COMBO_GATE_MIN_STATIONS)
          .map((f) => ({ code: f.code.toLowerCase(), genre: g.slug }));
      }),
    )
  ).flat();

  return [
    ...localizedEntries('/', 'daily', 1),
    ...localizedEntries('/genres', 'weekly', 0.8),
    ...localizedEntries('/countries', 'weekly', 0.8),
    ...localizedEntries('/trending', 'daily', 0.7),
    ...localizedEntries('/new', 'daily', 0.7),
    ...localizedEntries('/search', 'monthly', 0.4),
    ...localizedEntries('/support', 'monthly', 0.3),
    ...genres.flatMap((g) =>
      localizedEntries(`/genres/${g.slug}`, 'weekly', 0.7),
    ),
    ...gatedCountries.flatMap((c) =>
      localizedEntries(`/countries/${c.code.toLowerCase()}`, 'weekly', 0.7),
    ),
    ...combos.flatMap((c) =>
      localizedEntries(`/countries/${c.code}/${c.genre}`, 'weekly', 0.7),
    ),
    ...trendingGenres.flatMap((g) =>
      localizedEntries(`/trending/${g.slug}`, 'daily', 0.6),
    ),
    ...stations.flatMap((s) =>
      localizedEntries(
        `/stations/${s.slug}`,
        'weekly',
        0.6,
        s.updated_at ?? undefined,
      ),
    ),
  ];
}
