import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { storeToken } from '@/lib/admin/api';
import { getDashboardStats } from '@/lib/admin/dashboard';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe('getDashboardStats', () => {
  beforeEach(() => storeToken('jwt-1'));

  it('GETs /admin/dashboard/stats with Bearer', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          kpis: {
            stations_active: 1,
            stations_curated: 0,
            stations_broken: 0,
            avg_quality_active: 50,
          },
          quality_distribution: [],
          top_genres_curated: [],
          top_countries: [],
          recent_activity: [],
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        },
      ),
    );
    const result = await getDashboardStats();
    expect(result.kpis.stations_active).toBe(1);
    const [url, init] = fetchSpy.mock.calls[0]!;
    expect(String(url)).toBe(
      `${API_BASE}/api/v1/admin/dashboard/stats`,
    );
    const headers = (init as RequestInit).headers as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer jwt-1');
  });

  it('throws stats_failed_500 on error', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 500 }),
    );
    await expect(getDashboardStats()).rejects.toThrow('stats_failed_500');
  });
});
