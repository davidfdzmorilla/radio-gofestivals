'use client';

import { Suspense, useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import {
  type StationListItem,
  type StationListPage,
  type StationStatus,
  listStations,
  updateStation,
} from '@/lib/admin/stations';
import { CuratedToggle } from '@/components/admin/CuratedToggle';
import { Pagination } from '@/components/admin/Pagination';
import { StatusBadge } from '@/components/admin/StatusBadge';
import { cn } from '@/lib/utils';

const VALID_STATUSES: StationStatus[] = [
  'active',
  'broken',
  'inactive',
  'pending',
  'rejected',
  'duplicate',
];

function parseStatus(raw: string | null): StationStatus | undefined {
  if (!raw) return undefined;
  return VALID_STATUSES.includes(raw as StationStatus)
    ? (raw as StationStatus)
    : undefined;
}

function StationsListInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const status = parseStatus(searchParams.get('status'));
  const curatedRaw = searchParams.get('curated');
  const curated =
    curatedRaw === 'true' ? true : curatedRaw === 'false' ? false : undefined;
  const search = searchParams.get('search') ?? '';
  const page = Math.max(1, Number(searchParams.get('page') ?? '1') || 1);
  const sizeRaw = Number(searchParams.get('size') ?? '20') || 20;
  const size = [20, 50, 100].includes(sizeRaw) ? sizeRaw : 20;

  const [data, setData] = useState<StationListPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState(search);

  const updateUrl = useCallback(
    (updates: Record<string, string | number | null>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value === null || value === '') params.delete(key);
        else params.set(key, String(value));
      }
      const qs = params.toString();
      router.push(`/admin/stations${qs ? `?${qs}` : ''}`);
    },
    [router, searchParams],
  );

  // Keep input in sync if URL is changed externally (back/forward)
  useEffect(() => {
    setSearchInput(search);
  }, [search]);

  // Debounced search → URL update
  useEffect(() => {
    if (searchInput === search) return;
    const timer = setTimeout(() => {
      updateUrl({ search: searchInput || null, page: 1 });
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput, search, updateUrl]);

  // Fetch on filter change
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listStations({
      status,
      curated,
      search: search || undefined,
      page,
      size,
    })
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'unknown_error');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [status, curated, search, page, size]);

  async function toggleCurated(station: StationListItem) {
    const newValue = !station.curated;
    setData((prev) =>
      prev
        ? {
            ...prev,
            items: prev.items.map((s) =>
              s.id === station.id ? { ...s, curated: newValue } : s,
            ),
          }
        : prev,
    );
    try {
      await updateStation(station.id, {
        curated: newValue,
        notes: 'toggled from list',
      });
    } catch (err) {
      console.error('toggle_curated_failed', err);
      setData((prev) =>
        prev
          ? {
              ...prev,
              items: prev.items.map((s) =>
                s.id === station.id ? { ...s, curated: !newValue } : s,
              ),
            }
          : prev,
      );
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="font-display text-fg-0 text-2xl font-bold">Stations</h2>
        {data ? (
          <p className="text-fg-2 font-mono text-xs uppercase tracking-widest">
            {data.total} total · página {data.page} de {Math.max(1, data.pages)}
          </p>
        ) : null}
      </div>

      <div className="border-fg-3/40 bg-bg-2/40 flex flex-wrap items-center gap-3 rounded-lg border p-4">
        <input
          type="text"
          placeholder="Buscar por nombre o slug..."
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta min-w-[220px] flex-1 rounded-md border px-3 py-1.5 text-sm focus:outline-none"
        />

        <select
          value={status ?? ''}
          onChange={(e) => updateUrl({ status: e.target.value || null, page: 1 })}
          className="border-fg-3 bg-bg-1 text-fg-1 rounded-md border px-3 py-1.5 text-sm focus:outline-none"
        >
          <option value="">Status: All</option>
          <option value="active">Active</option>
          <option value="broken">Broken</option>
          <option value="inactive">Inactive</option>
          <option value="pending">Pending</option>
          <option value="rejected">Rejected</option>
          <option value="duplicate">Duplicate</option>
        </select>

        <select
          value={curatedRaw ?? ''}
          onChange={(e) => updateUrl({ curated: e.target.value || null, page: 1 })}
          className="border-fg-3 bg-bg-1 text-fg-1 rounded-md border px-3 py-1.5 text-sm focus:outline-none"
        >
          <option value="">Curated: All</option>
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select>

        <select
          value={String(size)}
          onChange={(e) => updateUrl({ size: e.target.value, page: 1 })}
          className="border-fg-3 bg-bg-1 text-fg-1 rounded-md border px-3 py-1.5 text-sm focus:outline-none"
        >
          <option value="20">20 / page</option>
          <option value="50">50 / page</option>
          <option value="100">100 / page</option>
        </select>
      </div>

      <div className="border-fg-3/40 bg-bg-2/40 overflow-hidden rounded-lg border">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-bg-3/50 text-fg-2 sticky top-0 font-mono text-[10px] uppercase tracking-widest">
              <tr>
                <th className="px-3 py-2 text-left">Name</th>
                <th className="px-3 py-2 text-left">Slug</th>
                <th className="px-3 py-2 text-left">Status</th>
                <th className="px-3 py-2 text-center">Curated</th>
                <th className="px-3 py-2 text-center">Country</th>
                <th className="px-3 py-2 text-right">Score</th>
                <th className="px-3 py-2 text-right">Streams</th>
                <th className="px-3 py-2 text-left">Last sync</th>
                <th className="px-3 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {error ? (
                <tr>
                  <td colSpan={9} className="text-warm py-8 text-center text-sm">
                    Error: {error}
                  </td>
                </tr>
              ) : null}
              {loading && !data ? (
                <tr>
                  <td
                    colSpan={9}
                    className="text-fg-2 py-8 text-center text-sm"
                  >
                    <Loader2 className="mx-auto animate-spin" size={20} />
                  </td>
                </tr>
              ) : null}
              {data && data.items.length === 0 && !loading ? (
                <tr>
                  <td
                    colSpan={9}
                    className="text-fg-2 py-8 text-center text-sm"
                  >
                    No stations match the filters.
                  </td>
                </tr>
              ) : null}
              {data?.items.map((station) => (
                <tr
                  key={station.id}
                  className={cn(
                    'border-fg-3/30 hover:bg-bg-3/40 border-t transition-colors',
                    loading && 'opacity-60',
                  )}
                >
                  <td className="text-fg-0 px-3 py-2 font-medium">
                    {station.name}
                  </td>
                  <td className="text-fg-2 px-3 py-2 font-mono text-xs">
                    {station.slug}
                  </td>
                  <td className="px-3 py-2">
                    <StatusBadge status={station.status} />
                  </td>
                  <td className="px-3 py-2 text-center">
                    <CuratedToggle
                      curated={station.curated}
                      onClick={() => toggleCurated(station)}
                      ariaLabel={`Toggle curated for ${station.name}`}
                    />
                  </td>
                  <td className="text-fg-2 px-3 py-2 text-center font-mono text-xs">
                    {station.country_code ?? '—'}
                  </td>
                  <td className="text-fg-1 px-3 py-2 text-right font-mono">
                    {station.quality_score}
                  </td>
                  <td className="text-fg-1 px-3 py-2 text-right font-mono">
                    {station.stream_count}
                  </td>
                  <td className="text-fg-2 px-3 py-2 font-mono text-xs">
                    {station.last_sync_at
                      ? new Date(station.last_sync_at).toLocaleDateString()
                      : '—'}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      type="button"
                      onClick={() =>
                        router.push(`/admin/stations/${station.id}`)
                      }
                      className="text-magenta hover:text-warm font-mono text-xs uppercase tracking-widest"
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {data && data.pages > 1 ? (
        <Pagination
          page={data.page}
          pages={data.pages}
          onChange={(p) => updateUrl({ page: p })}
        />
      ) : null}
    </div>
  );
}

export default function StationsListPage() {
  return (
    <Suspense
      fallback={
        <div className="text-fg-2 py-8 text-center font-mono text-xs uppercase tracking-widest">
          Loading…
        </div>
      }
    >
      <StationsListInner />
    </Suspense>
  );
}
