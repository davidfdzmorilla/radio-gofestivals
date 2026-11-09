import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GET as countriesGET } from '@/app/sitemap-countries.xml/route';
import { GET as genresGET } from '@/app/sitemap-genres.xml/route';
import { GET as indexGET } from '@/app/sitemap.xml/route';
import { GET as staticGET } from '@/app/sitemap-static.xml/route';
import { GET as stationsGET } from '@/app/sitemap-stations.xml/route';
import {
  LASTMOD_EPOCH,
  latestRealChange,
  realLastModified,
  resetSitemapMemoForTests,
} from '@/lib/sitemap-data';

const BEFORE = '2026-11-09T06:00:03Z'; // reescrito por el trigger antiguo: no es un cambio real
const AFTER_1 = '2026-11-10T08:00:00Z';
const AFTER_2 = '2026-11-12T09:30:00Z';

const st = (slug: string, cc: string, genres: string[], updated_at: string) => ({
  slug,
  logo_hash: 'h',
  country_code: cc,
  genres,
  quality_score: 70,
  updated_at,
});

const json = (v: unknown) => new Response(JSON.stringify(v), { status: 200 });

beforeEach(() => {
  resetSitemapMemoForTests();
  vi.stubGlobal('fetch', async (input: string) => {
    const url = String(input);
    if (url.includes('/facets/countries')) {
      return json(
        url.includes('genre=techno')
          ? [{ code: 'DE', station_count: 6 }, { code: 'FR', station_count: 6 }]
          : [{ code: 'DE', station_count: 9 }, { code: 'FR', station_count: 9 }],
      );
    }
    if (url.includes('/api/v1/genres')) {
      return json([
        { slug: 'techno', parent_id: null, station_count: 12, children: [] },
        { slug: 'house', parent_id: null, station_count: 12, children: [] },
      ]);
    }
    return json({
      pages: 1,
      items: [
        st('de-old', 'DE', ['techno'], BEFORE),
        st('de-new', 'DE', ['techno'], AFTER_1),
        st('fr-new', 'FR', ['house'], AFTER_2),
        st('fr-old', 'FR', ['techno'], BEFORE),
      ],
    });
  });
});
afterEach(() => vi.unstubAllGlobals());

const lastmodOf = (xml: string, loc: string) =>
  xml.match(new RegExp(`<loc>${loc.replace(/[/.]/g, '\\$&')}</loc>[\\s\\S]*?(?:<lastmod>([^<]+)</lastmod>)?\\s*</url>`))?.[1];

describe('realLastModified / latestRealChange', () => {
  it('solo cuenta fechas posteriores a la migración', () => {
    expect(realLastModified(BEFORE)).toBeUndefined();
    expect(realLastModified(LASTMOD_EPOCH)).toBeUndefined(); // estrictamente posterior
    expect(realLastModified(AFTER_1)).toBe(AFTER_1);
    expect(realLastModified(null)).toBeUndefined();
    expect(realLastModified('basura')).toBeUndefined();
  });

  it('el máximo ignora las anteriores y devuelve undefined si no queda ninguna', () => {
    const s = (u: string) => ({ ...st('x', 'DE', [], u) });
    expect(latestRealChange([s(BEFORE), s(AFTER_1), s(AFTER_2)])).toBe(AFTER_2);
    expect(latestRealChange([s(BEFORE)])).toBeUndefined();
    expect(latestRealChange([])).toBeUndefined();
  });
});

describe('lastmod en los sitemaps', () => {
  it('emisoras: su updated_at solo si es posterior; si no, sin lastmod', async () => {
    const xml = await (await stationsGET()).text();
    expect(lastmodOf(xml, 'https://radio.gofestivals.eu/es/stations/de-new')).toBe(AFTER_1);
    expect(lastmodOf(xml, 'https://radio.gofestivals.eu/es/stations/fr-new')).toBe(AFTER_2);
    expect(lastmodOf(xml, 'https://radio.gofestivals.eu/es/stations/de-old')).toBeUndefined();
    expect(lastmodOf(xml, 'https://radio.gofestivals.eu/es/stations/fr-old')).toBeUndefined();
  });

  it('géneros y países: máximo de sus emisoras visibles con cambio real', async () => {
    const genres = await (await genresGET()).text();
    // techno: de-old, de-new, fr-old -> el único cambio real es AFTER_1
    expect(lastmodOf(genres, 'https://radio.gofestivals.eu/es/genres/techno')).toBe(AFTER_1);
    expect(lastmodOf(genres, 'https://radio.gofestivals.eu/es/genres/house')).toBe(AFTER_2);

    const countries = await (await countriesGET()).text();
    expect(lastmodOf(countries, 'https://radio.gofestivals.eu/es/countries/de')).toBe(AFTER_1);
    expect(lastmodOf(countries, 'https://radio.gofestivals.eu/es/countries/fr')).toBe(AFTER_2);
    // combo DE×techno: de-new; combo FR×techno: solo fr-old (anterior) -> sin lastmod
    expect(lastmodOf(countries, 'https://radio.gofestivals.eu/es/countries/de/techno')).toBe(AFTER_1);
    expect(lastmodOf(countries, 'https://radio.gofestivals.eu/es/countries/fr/techno')).toBeUndefined();
  });

  it('estáticas e índice nunca llevan lastmod', async () => {
    expect(await (await staticGET()).text()).not.toContain('lastmod');
    expect(await (await indexGET()).text()).not.toContain('lastmod');
  });
});
