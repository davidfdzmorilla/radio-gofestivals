import { afterEach, describe, expect, it, vi } from 'vitest';
import { stationsForFestival } from '@/lib/festival-stations';

function station(id: string) {
  return {
    id, slug: `s-${id}`, name: `Station ${id}`, country_code: 'DE', city: null, curated: true,
    quality_score: 50, votes_local: 0, genres: ['techno'],
  };
}

/** La radio responde según el parámetro `genre` de la URL. */
function mockStations(byGenre: Record<string, string[] | 'fail'>) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const genre = new URL(String(input)).searchParams.get('genre') ?? '';
    const ids = byGenre[genre];
    if (ids === 'fail' || ids === undefined) return new Response('boom', { status: 500 });
    return new Response(
      JSON.stringify({ items: ids.map(station), total: ids.length, page: 1, size: ids.length, pages: 1 }),
      { status: 200 },
    );
  });
}

afterEach(() => vi.restoreAllMocks());

describe('stationsForFestival', () => {
  it('requests each main genre with spare room and picks proportionally', async () => {
    const spy = mockStations({
      techno: ['t1', 't2', 't3', 't4', 't5', 't6', 't7', 't8', 't9'],
      house: ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'],
      dnb: ['d1', 'd2', 'd3', 'd4', 'd5'],
    });
    const out = await stationsForFestival(
      [{ slug: 'techno', count: 5 }, { slug: 'house', count: 4 }, { slug: 'dnb', count: 1 }],
      6,
    );
    expect(out).toHaveLength(6);
    const urls = spy.mock.calls.map((c) => String(c[0]));
    expect(urls.some((u) => u.includes('genre=techno'))).toBe(true);
    expect(urls.some((u) => u.includes('genre=dnb'))).toBe(true);
    // el género dominante aporta más que el minoritario
    const byGenre = (p: string) => out.filter((s) => s.id.startsWith(p)).length;
    expect(byGenre('t')).toBeGreaterThanOrEqual(byGenre('h'));
    expect(byGenre('d')).toBe(1);
  });

  it('never repeats a station that two genres share', async () => {
    mockStations({
      techno: ['x1', 'x2', 'x3', 'x4', 'x5', 'x6', 'x7'],
      house: ['x1', 'x2', 'h3', 'h4', 'h5', 'h6', 'h7'],
    });
    const out = await stationsForFestival([{ slug: 'techno', count: 1 }, { slug: 'house', count: 1 }], 6);
    const ids = out.map((s) => s.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(out).toHaveLength(6);
  });

  it('skips a genre whose request fails and still returns the others', async () => {
    mockStations({ techno: ['t1', 't2', 't3', 't4', 't5', 't6', 't7', 't8'], house: 'fail' });
    const out = await stationsForFestival([{ slug: 'techno', count: 1 }, { slug: 'house', count: 1 }], 6);
    expect(out.length).toBeGreaterThan(0);
    expect(out.every((s) => s.id.startsWith('t'))).toBe(true);
  });

  it('returns [] when everything fails or there are no genres', async () => {
    mockStations({ techno: 'fail' });
    expect(await stationsForFestival([{ slug: 'techno', count: 1 }], 6)).toEqual([]);
    expect(await stationsForFestival([], 6)).toEqual([]);
  });
});
