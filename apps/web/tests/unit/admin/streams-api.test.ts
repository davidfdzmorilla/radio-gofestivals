import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { storeToken } from '@/lib/admin/api';
import {
  bulkStatusChange,
  promoteStreamToPrimary,
} from '@/lib/admin/streams';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

function lastCall() {
  const fetchSpy = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
  return fetchSpy.mock.calls[fetchSpy.mock.calls.length - 1]!;
}

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe('promoteStreamToPrimary', () => {
  beforeEach(() => storeToken('jwt-1'));

  it('PATCHes /admin/streams/{id}/promote-primary', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          promoted_stream_id: 'a',
          demoted_stream_id: 'b',
          station_id: 'c',
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        },
      ),
    );
    await promoteStreamToPrimary('abc');
    const [url, init] = lastCall();
    expect(String(url)).toBe(
      `${API_BASE}/api/v1/admin/streams/abc/promote-primary`,
    );
    expect((init as RequestInit).method).toBe('PATCH');
  });

  it('maps 404 to stream_not_found', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 404 }),
    );
    await expect(promoteStreamToPrimary('xx')).rejects.toThrow(
      'stream_not_found',
    );
  });

  it('maps 400 already_primary detail to typed error', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'already_primary' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    await expect(promoteStreamToPrimary('p')).rejects.toThrow(
      'already_primary',
    );
  });

  it('maps other errors to promote_failed_{status}', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 500 }),
    );
    await expect(promoteStreamToPrimary('p')).rejects.toThrow(
      'promote_failed_500',
    );
  });
});

describe('bulkStatusChange', () => {
  beforeEach(() => storeToken('jwt-1'));

  it('POSTs /admin/stations/bulk-status-change with body', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          affected: 2,
          skipped: 0,
          station_ids_affected: ['a', 'b'],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    await bulkStatusChange(['a', 'b'], 'inactive', 'cleanup');
    const [url, init] = lastCall();
    expect(String(url)).toBe(
      `${API_BASE}/api/v1/admin/stations/bulk-status-change`,
    );
    expect((init as RequestInit).method).toBe('POST');
    const body = JSON.parse(String((init as RequestInit).body));
    expect(body).toEqual({
      station_ids: ['a', 'b'],
      new_status: 'inactive',
      reason: 'cleanup',
    });
  });

  it('sends reason=null when not provided', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          affected: 1,
          skipped: 0,
          station_ids_affected: ['a'],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    await bulkStatusChange(['a'], 'inactive');
    const body = JSON.parse(
      String((lastCall()[1] as RequestInit).body),
    );
    expect(body.reason).toBeNull();
  });

  it('maps 422 to validation_failed', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: [{ msg: 'too_many' }] }), {
        status: 422,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    await expect(
      bulkStatusChange(new Array(101).fill('x'), 'inactive'),
    ).rejects.toThrow(/^validation_failed:/);
  });
});
