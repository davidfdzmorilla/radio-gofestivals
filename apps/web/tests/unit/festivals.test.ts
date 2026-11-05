import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  festivalCalendarUrl,
  festivalDescription,
  festivalImageSrc,
  festivalLocation,
  festivalPath,
  festivalPhase,
  festivalSlug,
  festivalUrl,
  formatFestivalDates,
  getAllUpcomingFestivals,
  getFestival,
  getUpcomingFestivals,
  safeHttpUrl,
} from '@/lib/festivals';
import { ApiError } from '@/lib/api';

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
    await getUpcomingFestivals({ genre: 'deep-house', limit: 4, now: NOW });
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
    const out = await getUpcomingFestivals({ genre: 'techno', limit: 2, now: NOW });
    expect(out.map((f) => f.name)).toEqual(['A', 'B']);
  });

  it('drops festivals that already ended but keeps one on its last day', async () => {
    mockFetch([
      festival({ id: 1, name: 'ended', start_date: '2026-11-01T00:00:00.000Z', end_date: '2026-11-04T00:00:00.000Z' }),
      festival({ id: 2, name: 'last-day', start_date: '2026-11-03T00:00:00.000Z', end_date: '2026-11-05T00:00:00.000Z' }),
    ]);
    const out = await getUpcomingFestivals({ genre: 'techno', now: NOW });
    expect(out.map((f) => f.name)).toEqual(['last-day']);
  });

  it('keeps both location variants so the page can localize them', async () => {
    mockFetch([festival()]);
    const [f] = await getUpcomingFestivals({ genre: 'techno', now: NOW });
    expect(festivalLocation(f!, 'en')).toBe('Brest, Brittany, France');
    expect(festivalLocation(f!, 'es')).toBe('Brest, Bretaña, Francia');
    expect(festivalLocation({ location: null, locationEn: null }, 'en')).toBeNull();
    expect(festivalLocation({ location: 'Solo es', locationEn: null }, 'en')).toBe('Solo es');
  });

  it('accepts numeric and string ids', async () => {
    mockFetch([festival({ id: 5 }), festival({ id: '6', name: 'Other', start_date: '2027-01-01T00:00:00.000Z' })]);
    const out = await getUpcomingFestivals({ genre: 'techno', now: NOW });
    expect(out.map((f) => f.id)).toEqual(['5', '6']);
  });

  it('skips malformed items instead of failing the whole module', async () => {
    mockFetch([{ id: 1 }, null, 'x', festival({ start_date: 'garbage' }), festival({ id: 9, name: 'OK' })]);
    const out = await getUpcomingFestivals({ genre: 'techno', now: NOW });
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
    await expect(getUpcomingFestivals({ genre: 'techno', now: NOW })).resolves.toEqual([]);
  });
});

describe('GOFESTIVALS_API_URL', () => {
  async function urlUsedWith(env: string | undefined): Promise<string> {
    vi.resetModules();
    if (env === undefined) vi.unstubAllEnvs();
    else vi.stubEnv('GOFESTIVALS_API_URL', env);
    const spy = mockFetch([]);
    const { getUpcomingFestivals: fresh } = await import('@/lib/festivals');
    await fresh({ genre: 'techno', now: NOW });
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

describe('festivalPath / festivalPhase / festivalDescription', () => {
  it('builds the internal path with the same slug rule', () => {
    expect(festivalPath({ id: '165', name: "Astropolis L'Hiver" })).toBe('/festivals/165/astropolis-l-hiver');
    expect(festivalPath({ id: '7', name: '★★★' })).toBe('/festivals/7/festival');
  });

  it('classifies upcoming / ongoing (including the last day) / ended', () => {
    const f = { startDate: '2026-11-03T00:00:00.000Z', endDate: '2026-11-05T00:00:00.000Z' };
    expect(festivalPhase(f, new Date('2026-11-02T23:59:00Z'))).toBe('upcoming');
    expect(festivalPhase(f, new Date('2026-11-03T00:00:00Z'))).toBe('ongoing');
    expect(festivalPhase(f, new Date('2026-11-05T20:00:00Z'))).toBe('ongoing');
    expect(festivalPhase(f, new Date('2026-11-06T00:00:00Z'))).toBe('ended');
    expect(festivalPhase({ startDate: '2026-11-05T00:00:00.000Z', endDate: null }, new Date('2026-11-05T12:00:00Z'))).toBe('ongoing');
  });

  it('prefers the description in the page language and falls back', () => {
    const d = { description: 'Descripción es', descriptionEn: 'English description' };
    expect(festivalDescription(d, 'en')).toBe('English description');
    expect(festivalDescription(d, 'es')).toBe('Descripción es');
    expect(festivalDescription({ description: 'Solo es', descriptionEn: null }, 'en')).toBe('Solo es');
    expect(festivalDescription({ description: null, descriptionEn: null }, 'es')).toBeNull();
  });
});

describe('getAllUpcomingFestivals', () => {
  it('asks for the API maximum (100) in one call', async () => {
    const spy = mockFetch([festival()]);
    await getAllUpcomingFestivals(NOW);
    expect(String(spy.mock.calls[0]![0])).toContain('limit=100');
    expect(spy).toHaveBeenCalledTimes(1);
  });
});

describe('getFestival', () => {
  const detail = {
    ...festival({ id: 17, name: 'Rave on Snow Festival', country_code: 'at', website: 'https://raveonsnow.com' }),
    imageUrl: 'https://proyecto-images-gofestivals.s3.eu-west-3.amazonaws.com/festivals/x/y.webp',
    description: 'Festival alpino.',
    description_en: 'Alpine festival.',
    Genres: [{ id: 1, name: 'Techno' }, { id: 2, name: 'House' }],
  };

  it('parses the detail into the normalized shape', async () => {
    const spy = mockFetch(detail);
    const f = await getFestival('17');
    expect(String(spy.mock.calls[0]![0])).toBe('https://api.gofestivals.es/api/festivals/17');
    expect(f).toMatchObject({
      id: '17',
      name: 'Rave on Snow Festival',
      countryCode: 'AT',
      website: 'https://raveonsnow.com',
      genres: ['Techno', 'House'],
      descriptionEn: 'Alpine festival.',
    });
    expect(f!.imageUrl).toContain('/festivals/x/y.webp');
  });

  it.each(['abc', '', '12abc', '-1', '1.5', '99999999999', '17/../1'])(
    'returns null for the non-numeric id %j without calling the API (it answers 500 there)',
    async (id) => {
      const spy = vi.spyOn(globalThis, 'fetch');
      expect(await getFestival(id)).toBeNull();
      expect(spy).not.toHaveBeenCalled();
    },
  );

  it('returns null on a 404 (festival does not exist)', async () => {
    mockFetch({ message: 'not found' }, { status: 404 });
    expect(await getFestival('999999')).toBeNull();
  });

  it('PROPAGATES outages instead of turning them into a cacheable 404', async () => {
    mockFetch({}, { status: 500 });
    await expect(getFestival('17')).rejects.toBeInstanceOf(ApiError);
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('down'));
    await expect(getFestival('17')).rejects.toBeInstanceOf(TypeError);
  });

  it('throws on a payload that is not a festival', async () => {
    mockFetch({ id: 17 });
    await expect(getFestival('17')).rejects.toThrow(/payload inválido/);
  });
});

describe('festivalImageSrc (next/image throws on unconfigured hosts)', () => {
  const ok = 'https://proyecto-images-gofestivals.s3.eu-west-3.amazonaws.com/festivals/x/y.webp';
  it('accepts only the gofestivals bucket over https under /festivals/', () => {
    expect(festivalImageSrc({ imageUrl: ok })).toBe(ok);
  });
  it.each([
    [null],
    [''],
    ['not a url'],
    ['http://proyecto-images-gofestivals.s3.eu-west-3.amazonaws.com/festivals/x.webp'],
    ['https://images.unsplash.com/photo-1'],
    ['https://evil.example/festivals/x.webp'],
    ['https://proyecto-images-gofestivals.s3.eu-west-3.amazonaws.com.evil.example/festivals/x.webp'],
    ['https://proyecto-images-gofestivals.s3.eu-west-3.amazonaws.com/other/x.webp'],
    ['https://user:pw@proyecto-images-gofestivals.s3.eu-west-3.amazonaws.com@evil.example/festivals/x.webp'],
  ])('rejects %j', (imageUrl) => {
    expect(festivalImageSrc({ imageUrl })).toBeNull();
  });
});

describe('safeHttpUrl (the official website ends up in an href)', () => {
  it('keeps http and https URLs', () => {
    expect(safeHttpUrl('https://raveonsnow.com')).toBe('https://raveonsnow.com/');
    expect(safeHttpUrl('  http://example.org/path?x=1 ')).toBe('http://example.org/path?x=1');
  });
  it.each([
    'javascript:alert(1)',
    'JaVaScRiPt:alert(1)',
    'data:text/html,<script>alert(1)</script>',
    'vbscript:msgbox(1)',
    'file:///etc/passwd',
    '//evil.example',
    '/relative/path',
    'raveonsnow.com',
    '',
    '   ',
  ])('rejects %j', (value) => {
    expect(safeHttpUrl(value)).toBeNull();
  });
  it('rejects null and undefined', () => {
    expect(safeHttpUrl(null)).toBeNull();
    expect(safeHttpUrl(undefined)).toBeNull();
  });
});
