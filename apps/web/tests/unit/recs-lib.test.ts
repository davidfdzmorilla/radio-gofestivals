import { afterEach, describe, expect, it, vi } from 'vitest';
import { getRecommendedStations, sendRecEvents } from '@/lib/recs';

const PAGE = {
  items: [],
  total: 0,
  page: 1,
  size: 0,
  pages: 0,
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('getRecommendedStations', () => {
  it('pasa client_id, locale y size como query params', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(PAGE), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await getRecommendedStations({
      clientId: 'abc-123',
      locale: 'es-ES',
      size: 12,
    });

    const url = fetchMock.mock.calls[0]?.[0] as string;
    expect(url).toContain('/api/v1/stations/recommended?');
    expect(url).toContain('client_id=abc-123');
    expect(url).toContain('locale=es-ES');
    expect(url).toContain('size=12');
  });

  it('omite client_id cuando no hay identidad (cold start)', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(PAGE), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await getRecommendedStations({ clientId: null, locale: 'en-GB' });

    const url = fetchMock.mock.calls[0]?.[0] as string;
    expect(url).not.toContain('client_id');
    expect(url).toContain('locale=en-GB');
  });
});

describe('sendRecEvents', () => {
  it('no envía nada sin client_id (sin consent no hay tracking)', () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    sendRecEvents({
      surface: 'home_for_you',
      clientId: null,
      events: [{ station_id: 'x', event_type: 'impression', slot: 0 }],
    });

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('envía el batch con keepalive', () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null));
    vi.stubGlobal('fetch', fetchMock);

    sendRecEvents({
      surface: 'station_similar',
      clientId: 'cid-1',
      events: [
        { station_id: 'a', event_type: 'impression', slot: 0 },
        { station_id: 'a', event_type: 'click', slot: 0 },
      ],
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/api/v1/recs/events');
    expect(init.keepalive).toBe(true);
    const body = JSON.parse(String(init.body)) as {
      surface: string;
      client_id: string;
      events: unknown[];
    };
    expect(body.surface).toBe('station_similar');
    expect(body.client_id).toBe('cid-1');
    expect(body.events).toHaveLength(2);
  });
});
