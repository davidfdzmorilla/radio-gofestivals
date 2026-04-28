import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getStationDetail,
  listStations,
  updateStation,
} from '@/lib/admin/stations';
import { storeToken } from '@/lib/admin/api';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

function lastUrl(): string {
  const fetchSpy = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
  return String(fetchSpy.mock.calls[fetchSpy.mock.calls.length - 1]![0]);
}

function lastInit(): RequestInit {
  const fetchSpy = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
  return fetchSpy.mock.calls[fetchSpy.mock.calls.length - 1]![1] as RequestInit;
}

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe('listStations', () => {
  beforeEach(() => {
    storeToken('jwt-1');
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ items: [], total: 0, page: 1, size: 20, pages: 0 }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        },
      ),
    );
  });

  it('builds URL without query params when no filters', async () => {
    await listStations();
    expect(lastUrl()).toBe(`${API_BASE}/api/v1/admin/stations`);
  });

  it('serializes filters into query string', async () => {
    await listStations({
      status: 'active',
      curated: true,
      search: 'yam',
      page: 2,
      size: 50,
    });
    const url = new URL(lastUrl());
    expect(url.searchParams.get('status')).toBe('active');
    expect(url.searchParams.get('curated')).toBe('true');
    expect(url.searchParams.get('search')).toBe('yam');
    expect(url.searchParams.get('page')).toBe('2');
    expect(url.searchParams.get('size')).toBe('50');
  });

  it('serializes curated=false (not omitted)', async () => {
    await listStations({ curated: false });
    expect(new URL(lastUrl()).searchParams.get('curated')).toBe('false');
  });

  it('attaches Bearer token', async () => {
    await listStations();
    const headers = lastInit().headers as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer jwt-1');
  });

  it('throws on non-2xx', async () => {
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      new Response('', { status: 500 }),
    );
    await expect(listStations()).rejects.toThrow('list_stations_failed_500');
  });
});

describe('updateStation', () => {
  beforeEach(() => {
    storeToken('jwt-1');
  });

  it('sends PATCH with JSON body', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({}), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    await updateStation('abc', { curated: true, notes: 'x' });
    const init = lastInit();
    expect(init.method).toBe('PATCH');
    expect(init.body).toBe(JSON.stringify({ curated: true, notes: 'x' }));
    expect(lastUrl()).toBe(`${API_BASE}/api/v1/admin/stations/abc`);
  });

  it('maps 409 to slug_conflict', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 409 }),
    );
    await expect(updateStation('abc', { slug: 'taken' })).rejects.toThrow(
      'slug_conflict',
    );
  });

  it('maps 404 to not_found', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 404 }),
    );
    await expect(updateStation('abc', { curated: true })).rejects.toThrow(
      'not_found',
    );
  });

  it('maps 400 to invalid_payload', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 400 }),
    );
    await expect(updateStation('abc', { genre_ids: [99] })).rejects.toThrow(
      'invalid_payload',
    );
  });
});

describe('getStationDetail', () => {
  beforeEach(() => {
    storeToken('jwt-1');
  });

  it('GETs the right URL and returns JSON', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ id: 'abc', name: 'X' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    const detail = await getStationDetail('abc');
    expect(lastUrl()).toBe(`${API_BASE}/api/v1/admin/stations/abc`);
    expect(detail.id).toBe('abc');
  });

  it('maps 404 to not_found', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 404 }),
    );
    await expect(getStationDetail('missing')).rejects.toThrow('not_found');
  });
});
