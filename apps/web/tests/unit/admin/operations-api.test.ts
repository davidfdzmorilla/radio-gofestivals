import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { storeToken } from '@/lib/admin/api';
import {
  getCatalog,
  getJob,
  listJobs,
  runCommand,
} from '@/lib/admin/operations';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

function lastCall() {
  const fetchSpy = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
  return fetchSpy.mock.calls[fetchSpy.mock.calls.length - 1]!;
}

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe('getCatalog', () => {
  beforeEach(() => storeToken('jwt-1'));

  it('GETs /admin/operations/catalog', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    await getCatalog();
    expect(String(lastCall()[0])).toBe(
      `${API_BASE}/api/v1/admin/operations/catalog`,
    );
  });

  it('throws on non-2xx', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 500 }),
    );
    await expect(getCatalog()).rejects.toThrow('catalog_failed_500');
  });
});

describe('runCommand', () => {
  beforeEach(() => storeToken('jwt-1'));

  it('POSTs /admin/operations/run with JSON body', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ id: 1, command: 'x', status: 'pending' }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    await runCommand('snapshot_clickcounts');
    const [url, init] = lastCall();
    expect(String(url)).toBe(`${API_BASE}/api/v1/admin/operations/run`);
    expect((init as RequestInit).method).toBe('POST');
    expect((init as RequestInit).body).toBe(
      JSON.stringify({ command: 'snapshot_clickcounts', params: null }),
    );
  });

  it('forwards params object', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ id: 9 }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    await runCommand('auto_curate', { dry_run: true, limit: 10 });
    expect((lastCall()[1] as RequestInit).body).toBe(
      JSON.stringify({
        command: 'auto_curate',
        params: { dry_run: true, limit: 10 },
      }),
    );
  });

  it('maps 400 to command_not_allowed', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 400 }),
    );
    await expect(runCommand('rm_rf')).rejects.toThrow('command_not_allowed');
  });

  it('maps 422 to invalid_params with detail', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ detail: 'invalid_params: missing email' }),
        { status: 422, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    await expect(
      runCommand('auto_curate', { limit: 10 }),
    ).rejects.toThrow(/^invalid_params:/);
  });
});

describe('listJobs', () => {
  beforeEach(() => storeToken('jwt-1'));

  it('GETs /admin/operations/jobs without params', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ items: [], total: 0, page: 1, size: 20, pages: 0 }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    await listJobs();
    expect(String(lastCall()[0])).toBe(
      `${API_BASE}/api/v1/admin/operations/jobs`,
    );
  });

  it('serializes filters', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ items: [], total: 0, page: 1, size: 20, pages: 0 }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    await listJobs({ size: 50, status: 'running', page: 2 });
    const url = new URL(String(lastCall()[0]));
    expect(url.searchParams.get('size')).toBe('50');
    expect(url.searchParams.get('status')).toBe('running');
    expect(url.searchParams.get('page')).toBe('2');
  });
});

describe('getJob', () => {
  beforeEach(() => storeToken('jwt-1'));

  it('maps 404 to not_found', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 404 }),
    );
    await expect(getJob(999)).rejects.toThrow('not_found');
  });

  it('returns the parsed job', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ id: 7, command: 'x', status: 'success' }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    const result = await getJob(7);
    expect(result.id).toBe(7);
  });
});
