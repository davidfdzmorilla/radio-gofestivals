import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GET as indexGET } from '@/app/sitemap.xml/route';
import { GET as v2GET } from '@/app/sitemap-v2.xml/route';
import { GET as stationsGET } from '@/app/sitemap-stations.xml/route';
import { GET as countriesGET } from '@/app/sitemap-countries.xml/route';
import { GET as genresGET } from '@/app/sitemap-genres.xml/route';
import { GET as staticGET } from '@/app/sitemap-static.xml/route';
import robots from '@/app/robots';
import { resetSitemapMemoForTests } from '@/lib/sitemap-data';
import { renderUrlset, SITEMAP_MAX_URLS } from '@/lib/sitemap-xml';

const json = (v: unknown) => new Response(JSON.stringify(v), { status: 200 });

beforeEach(() => {
  resetSitemapMemoForTests();
  vi.stubGlobal('fetch', async (input: string) => {
    const url = String(input);
    if (url.includes('/facets/countries')) {
      return json(url.includes('genre=techno') ? [{ code: 'DE', station_count: 6 }] : [{ code: 'DE', station_count: 9 }]);
    }
    if (url.includes('/api/v1/genres')) {
      return json([{ slug: 'techno', parent_id: null, station_count: 12, children: [] }]);
    }
    return json({
      pages: 1,
      items: [
        { slug: 'a', logo_hash: 'h', country_code: 'DE', genres: ['techno'], quality_score: 70, updated_at: '2026-11-01T10:00:00Z' },
        { slug: 'b', logo_hash: 'h', country_code: 'DE', genres: ['techno'], quality_score: 70, updated_at: '2026-11-05T10:00:00Z' },
      ],
    });
  });
});
afterEach(() => vi.unstubAllGlobals());

describe('índice de sitemaps', () => {
  it('es un sitemapindex con los cuatro hijos y sin lastmod', async () => {
    const res = await indexGET();
    const xml = await res.text();
    expect(xml).toContain('<sitemapindex');
    for (const c of ['static', 'genres', 'countries', 'stations']) {
      expect(xml).toContain(`<loc>https://radio.gofestivals.eu/sitemap-${c}.xml</loc>`);
    }
    expect(xml).not.toContain('<lastmod>');
    expect(xml).not.toContain('<urlset');
  });

  it('cada hijo es un urlset con hreflang es/en/x-default, sin changefreq ni priority', async () => {
    for (const get of [staticGET, genresGET, countriesGET, stationsGET]) {
      const xml = await (await get()).text();
      expect(xml).toContain('<urlset');
      expect(xml).toContain('hreflang="x-default"');
      expect(xml).not.toMatch(/changefreq|priority/);
      expect(xml).not.toContain('/festivals');
    }
    const stations = await (await stationsGET()).text();
    expect(stations).toContain('<loc>https://radio.gofestivals.eu/es/stations/a</loc>');
  });

  it('ningún sitemap emite lastmod mientras updated_at no sea una fecha de cambio real', async () => {
    for (const get of [indexGET, staticGET, genresGET, countriesGET, stationsGET]) {
      expect(await (await get()).text()).not.toContain('lastmod');
    }
  });

  it('el renderizador sigue soportando lastmod para cuando se recupere', () => {
    const xml = renderUrlset([
      { url: 'https://x/a', alternates: {}, lastModified: '2026-11-01T00:00:00Z' },
    ]);
    expect(xml).toContain('<lastmod>2026-11-01T00:00:00Z</lastmod>');
  });

  it('rechaza un urlset por encima de 50.000 URLs', () => {
    const e = { url: 'https://x/', alternates: {} };
    expect(() => renderUrlset(Array.from({ length: SITEMAP_MAX_URLS + 1 }, () => e))).toThrow();
  });
});

describe('sitemap-v2.xml y robots', () => {
  it('sitemap-v2.xml redirige con 301 al índice (URL absoluta)', () => {
    const res = v2GET();
    expect(res.status).toBe(301);
    expect(res.headers.get('location')).toBe('https://radio.gofestivals.eu/sitemap.xml');
  });

  it('robots.txt declara un único Sitemap y no usa Host', () => {
    const r = robots();
    expect(r.sitemap).toBe('https://radio.gofestivals.eu/sitemap.xml');
    expect('host' in r).toBe(false);
  });
});
