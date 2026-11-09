import { afterEach, describe, expect, it, vi } from 'vitest';
import { buildSitemapEntries } from '@/lib/sitemap-data';
import { isStationIndexable } from '@/lib/indexability';

type S = {
  slug: string;
  logo_hash: string | null;
  country_code: string | null;
  genres: string[];
  quality_score: number;
  updated_at: string;
};
const st = (slug: string, over: Partial<S> = {}): S => ({
  slug,
  logo_hash: 'h',
  country_code: 'DE',
  genres: ['techno'],
  quality_score: 60,
  updated_at: '2026-11-01T00:00:00Z',
  ...over,
});

const STATIONS: S[] = [
  st('good'),
  st('low-quality', { quality_score: 49 }),
  st('no-logo', { logo_hash: null }),
  st('radio-onimai', { quality_score: 40 }), // allowlist
];
const genre = (slug: string, n: number, parent: number | null = null) => ({
  slug, parent_id: parent, station_count: n, children: [],
});

function mockApi() {
  vi.stubGlobal('fetch', async (input: string) => {
    const url = String(input);
    const json = (v: unknown) => new Response(JSON.stringify(v), { status: 200 });
    if (url.includes('/api/v1/stations/facets/countries')) {
      if (url.includes('genre=techno'))
        return json([{ code: 'DE', station_count: 5 }, { code: 'FR', station_count: 4 }]);
      return json([
        { code: 'DE', station_count: 9 },
        { code: 'SE', station_count: 4 }, // existe pero noindex
        { code: 'PL', station_count: 5 },
      ]);
    }
    if (url.includes('/api/v1/genres')) return json([genre('techno', 10), genre('tiny', 7)]);
    if (url.includes('/api/v1/stations')) return json({ items: STATIONS, pages: 1 });
    return new Response('', { status: 404 });
  });
}

afterEach(() => vi.unstubAllGlobals());

describe('buildSitemapEntries respeta lib/indexability', () => {
  it('lista solo lo indexable, una vez por idioma', async () => {
    mockApi();
    const urls = (await buildSitemapEntries()).map((e) => e.url.replace('https://radio.gofestivals.eu', ''));
    const es = urls.filter((u) => u.startsWith('/es'));

    // emisoras: las mismas que isStationIndexable acepta
    const expected = STATIONS.filter((s) => isStationIndexable({ ...s, genreCount: s.genres.length })).map((s) => `/es/stations/${s.slug}`);
    expect(es.filter((u) => u.startsWith('/es/stations/')).sort()).toEqual(expected.sort());
    expect(expected).toEqual(['/es/stations/good', '/es/stations/radio-onimai']);

    expect(es).toContain('/es/genres/techno');
    expect(es).not.toContain('/es/genres/tiny');
    expect(es).toContain('/es/countries/de');
    expect(es).toContain('/es/countries/pl');
    expect(es).not.toContain('/es/countries/se');
    expect(es).toContain('/es/countries/de/techno');
    expect(es).not.toContain('/es/countries/fr/techno');
  });

  it('no incluye festivales, /new ni /search; el resto de estáticas sí', async () => {
    mockApi();
    const urls = (await buildSitemapEntries()).map((e) => e.url);
    expect(urls.some((u) => u.includes('/festivals'))).toBe(false);
    expect(urls.some((u) => u.endsWith('/es/new') || u.endsWith('/es/search'))).toBe(false);
    expect(urls).toContain('https://radio.gofestivals.eu/es/for-stations');
    expect(urls).toContain('https://radio.gofestivals.eu/es');
  });
});

describe('x-default del sitemap coincide con el de las páginas', () => {
  it('portada -> /, resto -> /en/...', async () => {
    mockApi();
    const entries = await buildSitemapEntries();
    const home = entries.find((e) => e.url.endsWith('/es'));
    expect(home?.alternates?.languages?.['x-default']).toBe('https://radio.gofestivals.eu');
    const genre = entries.find((e) => e.url.endsWith('/es/genres/techno'));
    expect(genre?.alternates?.languages?.['x-default']).toBe('https://radio.gofestivals.eu/en/genres/techno');
  });
});
