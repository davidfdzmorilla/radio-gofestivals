import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  festivalCalendarUrl,
  festivalSlug,
  festivalUrl,
  formatFestivalDates,
  getUpcomingFestivals,
} from '@/lib/festivals';

const NOW = new Date('2026-11-05T12:00:00Z');

function festival(over: Record<string, unknown> = {}) {
  return {
    id: 165,
    name: "Astropolis L'Hiver",
    start_date: '2026-12-05T00:00:00.000Z',
    end_date: '2026-12-09T00:00:00.000Z',
    location: 'Brest, Bretaña, Francia',
    location_en: 'Brest, Brittany, France',
    ...over,
  };
}

function mockFetch(body: unknown, init: ResponseInit = { status: 200 }) {
  return vi
    .spyOn(globalThis, 'fetch')
    .mockResolvedValue(new Response(JSON.stringify(body), init));
}

afterEach(() => vi.restoreAllMocks());

describe('festivalSlug (mismo algoritmo que generateSlug de gofestivals)', () => {
  it.each([
    ["Astropolis L'Hiver", 'astropolis-l-hiver'],
    ['Sónar Barcelona', 'sonar-barcelona'],
    ['Tomorrowland Winter', 'tomorrowland-winter'],
    ['  --Rave on Snow!!  ', 'rave-on-snow'],
    ['Ñu & Café 2027', 'nu-cafe-2027'],
    ['★★★', ''],
  ])('%s -> %s', (name, expected) => {
    expect(festivalSlug(name)).toBe(expected);
  });
});

describe('festivalUrl / festivalCalendarUrl', () => {
  it('uses gofestivals.es/es for Spanish and gofestivals.eu/en otherwise', () => {
    const f = { id: '165', name: "Astropolis L'Hiver" };
    expect(festivalUrl('es', f)).toBe('https://gofestivals.es/es/festival/165/astropolis-l-hiver');
    expect(festivalUrl('en', f)).toBe('https://gofestivals.eu/en/festival/165/astropolis-l-hiver');
    expect(festivalUrl('de', f)).toBe('https://gofestivals.eu/en/festival/165/astropolis-l-hiver');
    expect(festivalCalendarUrl('es')).toBe('https://gofestivals.es/es/calendar');
    expect(festivalCalendarUrl('en')).toBe('https://gofestivals.eu/en/calendar');
  });

  it('never produces an empty slug segment', () => {
    expect(festivalUrl('en', { id: '7', name: '★★★' })).toBe(
      'https://gofestivals.eu/en/festival/7/festival',
    );
  });
});

describe('formatFestivalDates', () => {
  it('formats in UTC so a midnight-UTC date never shifts a day', () => {
    const out = formatFestivalDates('en', '2026-12-05T00:00:00.000Z', null);
    expect(out).toContain('5');
    expect(out).toContain('2026');
  });
  it('collapses a range and a same-day event', () => {
    const range = formatFestivalDates('en', '2026-12-05T00:00:00.000Z', '2026-12-09T00:00:00.000Z');
    expect(range).toMatch(/5.*9/);
    expect(formatFestivalDates('en', '2026-12-05T00:00:00.000Z', '2026-12-05T00:00:00.000Z')).toBe(
      formatFestivalDates('en', '2026-12-05T00:00:00.000Z', null),
    );
  });
  it('returns an empty string for an invalid date', () => {
    expect(formatFestivalDates('en', 'not-a-date', null)).toBe('');
  });
});

describe('getUpcomingFestivals', () => {
  beforeEach(() => vi.useRealTimers());

  it('asks the API for upcoming festivals of the genre with a margin, cached 1h', async () => {
    const spy = mockFetch([festival()]);
    await getUpcomingFestivals({ genre: 'deep-house', locale: 'en', limit: 4, now: NOW });
    const [url, init] = spy.mock.calls[0]!;
    expect(String(url)).toContain('https://api.gofestivals.es/api/festivals?');
    expect(String(url)).toContain('genre=deep-house');
    expect(String(url)).toContain('upcoming=true');
    expect(String(url)).toContain('limit=8');
    expect((init as { next?: { revalidate?: number } }).next?.revalidate).toBe(3600);
    expect((init as RequestInit).signal).toBeInstanceOf(AbortSignal);
  });

  it('sorts by start date and respects the limit', async () => {
    mockFetch([
      festival({ id: 3, name: 'C', start_date: '2027-03-01T00:00:00.000Z', end_date: null }),
      festival({ id: 1, name: 'A', start_date: '2026-12-01T00:00:00.000Z', end_date: null }),
      festival({ id: 2, name: 'B', start_date: '2027-01-01T00:00:00.000Z', end_date: null }),
    ]);
    const out = await getUpcomingFestivals({ genre: 'techno', locale: 'en', limit: 2, now: NOW });
    expect(out.map((f) => f.name)).toEqual(['A', 'B']);
  });

  it('drops festivals that already ended but keeps one on its last day', async () => {
    mockFetch([
      festival({ id: 1, name: 'ended', start_date: '2026-11-01T00:00:00.000Z', end_date: '2026-11-04T00:00:00.000Z' }),
      festival({ id: 2, name: 'last-day', start_date: '2026-11-03T00:00:00.000Z', end_date: '2026-11-05T00:00:00.000Z' }),
    ]);
    const out = await getUpcomingFestivals({ genre: 'techno', locale: 'en', now: NOW });
    expect(out.map((f) => f.name)).toEqual(['last-day']);
  });

  it('localizes the location', async () => {
    mockFetch([festival()]);
    const en = await getUpcomingFestivals({ genre: 'techno', locale: 'en', now: NOW });
    expect(en[0]!.location).toBe('Brest, Brittany, France');
    mockFetch([festival()]);
    const es = await getUpcomingFestivals({ genre: 'techno', locale: 'es', now: NOW });
    expect(es[0]!.location).toBe('Brest, Bretaña, Francia');
  });

  it('accepts numeric and string ids', async () => {
    mockFetch([festival({ id: 5 }), festival({ id: '6', name: 'Other', start_date: '2027-01-01T00:00:00.000Z' })]);
    const out = await getUpcomingFestivals({ genre: 'techno', locale: 'en', now: NOW });
    expect(out.map((f) => f.id)).toEqual(['5', '6']);
  });

  it('skips malformed items instead of failing the whole module', async () => {
    mockFetch([{ id: 1 }, null, 'x', festival({ start_date: 'garbage' }), festival({ id: 9, name: 'OK' })]);
    const out = await getUpcomingFestivals({ genre: 'techno', locale: 'en', now: NOW });
    expect(out.map((f) => f.name)).toEqual(['OK']);
  });

  it.each([
    ['a non-array payload', () => mockFetch({ error: 'x' })],
    ['an HTTP 500', () => mockFetch([], { status: 500 })],
    ['a network error', () => vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('down'))],
    ['a timeout', () => vi.spyOn(globalThis, 'fetch').mockRejectedValue(new DOMException('t', 'TimeoutError'))],
    ['invalid JSON', () => vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('<html>', { status: 200 }))],
  ])('returns [] (never throws) on %s', async (_label, arrange) => {
    arrange();
    await expect(getUpcomingFestivals({ genre: 'techno', locale: 'en', now: NOW })).resolves.toEqual([]);
  });
});

describe('GOFESTIVALS_API_URL', () => {
  async function urlUsedWith(env: string | undefined): Promise<string> {
    vi.resetModules();
    if (env === undefined) vi.unstubAllEnvs();
    else vi.stubEnv('GOFESTIVALS_API_URL', env);
    const spy = mockFetch([]);
    const { getUpcomingFestivals: fresh } = await import('@/lib/festivals');
    await fresh({ genre: 'techno', locale: 'en', now: NOW });
    return String(spy.mock.calls[0]![0]);
  }
  afterEach(() => vi.unstubAllEnvs());

  it('falls back to the public API when unset or empty', async () => {
    expect(await urlUsedWith(undefined)).toMatch(/^https:\/\/api\.gofestivals\.es\/api\/festivals\?/);
    expect(await urlUsedWith('')).toMatch(/^https:\/\/api\.gofestivals\.es\/api\/festivals\?/);
    expect(await urlUsedWith('   ')).toMatch(/^https:\/\/api\.gofestivals\.es\/api\/festivals\?/);
  });

  it('uses a custom base and tolerates a trailing slash', async () => {
    expect(await urlUsedWith('http://staging.example:4000/')).toMatch(
      /^http:\/\/staging\.example:4000\/api\/festivals\?/,
    );
  });
});
