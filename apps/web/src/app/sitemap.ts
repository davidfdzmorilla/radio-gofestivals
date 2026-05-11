import type { MetadataRoute } from 'next';

const SITE = 'https://radio.gofestivals.eu';
const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const LOCALES = ['es', 'en'] as const;
const DEFAULT_LOCALE: (typeof LOCALES)[number] = 'es';
const PAGE_SIZE = 50;
const REVALIDATE_SECONDS = 86_400;

// Next.js statically analyses this export and requires a literal number.
export const revalidate = 86_400;

type Station = { slug: string };
type StationPage = { items: Station[]; pages: number };
type Genre = { slug: string; children?: Genre[] };

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
): MetadataRoute.Sitemap {
  const languages: Record<string, string> = Object.fromEntries(
    LOCALES.map((l) => [l, `${SITE}/${l}${path}`]),
  );
  languages['x-default'] = `${SITE}/${DEFAULT_LOCALE}${path}`;
  return LOCALES.map((locale) => ({
    url: `${SITE}/${locale}${path}`,
    changeFrequency,
    priority,
    alternates: { languages },
  }));
}

async function fetchAllStations(): Promise<Station[]> {
  const first = await fetch(
    `${API}/api/v1/stations?size=${PAGE_SIZE}&page=1`,
    { next: { revalidate: REVALIDATE_SECONDS } },
  );
  if (!first.ok) return [];
  const firstPage = (await first.json()) as StationPage;
  const out: Station[] = [...firstPage.items];

  const remaining = await Promise.all(
    Array.from({ length: Math.max(0, firstPage.pages - 1) }, (_, i) =>
      fetch(`${API}/api/v1/stations?size=${PAGE_SIZE}&page=${i + 2}`, {
        next: { revalidate: REVALIDATE_SECONDS },
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
    next: { revalidate: REVALIDATE_SECONDS },
  });
  if (!res.ok) return [];
  return flattenGenres((await res.json()) as Genre[]);
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [stations, genres] = await Promise.all([
    fetchAllStations(),
    fetchAllGenres(),
  ]);

  return [
    ...localizedEntries('/', 'daily', 1),
    ...localizedEntries('/genres', 'weekly', 0.8),
    ...localizedEntries('/support', 'monthly', 0.3),
    ...genres.flatMap((g) =>
      localizedEntries(`/genres/${g.slug}`, 'weekly', 0.7),
    ),
    ...stations.flatMap((s) =>
      localizedEntries(`/stations/${s.slug}`, 'weekly', 0.6),
    ),
  ];
}
