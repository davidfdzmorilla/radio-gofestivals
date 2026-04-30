'use client';

import { Suspense, useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import {
  useParams,
  useRouter,
  useSearchParams,
} from 'next/navigation';
import { ArrowLeft, Check, ExternalLink, Pencil, Star } from 'lucide-react';
import {
  type StationDetail,
  getStationDetail,
} from '@/lib/admin/stations';
import { PromotePrimaryButton } from '@/components/admin/PromotePrimaryButton';
import { StatusBadge } from '@/components/admin/StatusBadge';
import { cn } from '@/lib/utils';

export default function StationDetailPage() {
  return (
    <Suspense
      fallback={
        <div className="text-fg-2 py-12 text-center font-mono text-xs uppercase tracking-widest">
          Loading…
        </div>
      }
    >
      <StationDetailInner />
    </Suspense>
  );
}

function StationDetailInner() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const stationId = params.id;
  const justSaved = searchParams.get('saved') === '1';

  const [station, setStation] = useState<StationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!stationId) return;
    try {
      const data = await getStationDetail(stationId);
      setStation(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'unknown_error');
    }
  }, [stationId]);

  useEffect(() => {
    if (!stationId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    getStationDetail(stationId)
      .then((data) => {
        if (!cancelled) setStation(data);
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
  }, [stationId]);

  if (loading) {
    return (
      <div className="text-fg-2 py-12 text-center font-mono text-xs uppercase tracking-widest">
        Loading…
      </div>
    );
  }

  if (error === 'not_found' || !station) {
    return (
      <div className="space-y-4">
        <BackButton onClick={() => router.back()} />
        <p className="text-warm font-mono text-sm">
          Station not found.
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <BackButton onClick={() => router.back()} />
        <p className="text-warm font-mono text-sm">Error: {error}</p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-6">
      <BackButton onClick={() => router.back()} />

      {justSaved ? (
        <div
          role="status"
          className="border-cyan-soft bg-cyan-soft/40 text-cyan inline-flex items-center gap-2 rounded-md border px-3 py-2 font-mono text-xs uppercase tracking-widest"
        >
          <Check size={14} />
          Cambios guardados
        </div>
      ) : null}

      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-fg-0 text-3xl font-bold">
            {station.name}
          </h1>
          <p className="text-fg-2 mt-1 font-mono text-xs uppercase tracking-widest">
            {station.slug}
          </p>
        </div>
        <Link
          href={`/admin/stations/${station.id}/edit`}
          className="bg-wave text-fg-0 shadow-sticker hover:bg-magenta hover:shadow-sticker-magenta inline-flex items-center gap-2 rounded-md px-4 py-2 font-display text-sm font-medium transition-all"
        >
          <Pencil size={14} />
          Edit
        </Link>
      </div>

      <Section title="Info">
        <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
          <InfoRow label="Status">
            <StatusBadge status={station.status} />
          </InfoRow>
          <InfoRow label="Curated">
            {station.curated ? (
              <span className="text-magenta font-mono text-xs uppercase tracking-widest">
                ✓ Yes
              </span>
            ) : (
              <span className="text-fg-2 font-mono text-xs uppercase tracking-widest">
                No
              </span>
            )}
          </InfoRow>
          <InfoRow label="Country">{station.country_code ?? '—'}</InfoRow>
          <InfoRow label="City">{station.city ?? '—'}</InfoRow>
          <InfoRow label="Language">{station.language ?? '—'}</InfoRow>
          <InfoRow label="Homepage">
            {station.homepage_url ? (
              <a
                href={station.homepage_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-magenta hover:text-warm inline-flex max-w-[260px] items-center gap-1 truncate"
              >
                <span className="truncate">{station.homepage_url}</span>
                <ExternalLink size={12} />
              </a>
            ) : (
              '—'
            )}
          </InfoRow>
          <InfoRow label="Quality score">{station.quality_score}</InfoRow>
          <InfoRow label="Clickcount">
            {station.clickcount.toLocaleString()}
          </InfoRow>
          <InfoRow label="Votes">{station.votes.toLocaleString()}</InfoRow>
          <InfoRow label="Click trend">{station.click_trend}</InfoRow>
          <InfoRow label="Failed checks">{station.failed_checks}</InfoRow>
          <InfoRow label="Last check">
            {station.last_check_at
              ? new Date(station.last_check_at).toLocaleString()
              : '—'}
          </InfoRow>
          <InfoRow label="Last sync">
            {station.last_sync_at
              ? new Date(station.last_sync_at).toLocaleString()
              : '—'}
          </InfoRow>
          <InfoRow label="Created">
            {new Date(station.created_at).toLocaleString()}
          </InfoRow>
          {station.last_error ? (
            <InfoRow label="Last error">
              <span className="text-warm font-mono text-xs">
                {station.last_error}
              </span>
            </InfoRow>
          ) : null}
        </dl>
      </Section>

      <Section title={`Streams (${station.streams.length})`}>
        {station.streams.length === 0 ? (
          <p className="text-fg-2 text-sm">No streams.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-fg-2 font-mono text-[10px] uppercase tracking-widest">
                <tr className="border-fg-3/30 border-b">
                  <th className="py-2 text-left">URL</th>
                  <th className="py-2 text-left">Codec</th>
                  <th className="py-2 text-right">Bitrate</th>
                  <th className="py-2 text-center">Primary</th>
                  <th className="py-2 text-left">Status</th>
                  <th className="py-2 text-right">Failed</th>
                  <th className="py-2 text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {station.streams.map((s) => (
                  <tr key={s.id} className="border-fg-3/20 border-t">
                    <td className="text-fg-1 max-w-md truncate py-1.5 font-mono text-xs">
                      {s.url}
                    </td>
                    <td className="text-fg-1 py-1.5 font-mono text-xs">
                      {s.codec ?? '—'}
                    </td>
                    <td className="text-fg-1 py-1.5 text-right font-mono">
                      {s.bitrate ?? '—'}
                    </td>
                    <td className="py-1.5 text-center">
                      {s.is_primary ? (
                        <Star
                          size={14}
                          className="text-magenta mx-auto"
                          fill="currentColor"
                        />
                      ) : null}
                    </td>
                    <td className="py-1.5">
                      <StatusBadge status={s.status} />
                    </td>
                    <td className="text-fg-2 py-1.5 text-right font-mono">
                      {s.failed_checks}
                    </td>
                    <td className="py-1.5 text-right">
                      {s.is_primary ? (
                        <span className="text-fg-3 font-mono text-[10px] uppercase tracking-widest">
                          —
                        </span>
                      ) : (
                        <PromotePrimaryButton
                          streamId={s.id}
                          onPromoted={refresh}
                        />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section title={`Genres (${station.genres.length})`}>
        {station.genres.length === 0 ? (
          <p className="text-fg-2 text-sm">No genres assigned.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {station.genres.map((g) => (
              <span
                key={g.genre_id}
                className="bg-bg-3 text-fg-1 rounded-full px-2.5 py-1 font-mono text-xs"
                title={`Confidence ${g.confidence}, source ${g.source}`}
              >
                {g.name}
              </span>
            ))}
          </div>
        )}
      </Section>

      <Section title="Audit history (last 20)">
        {station.audit.length === 0 ? (
          <p className="text-fg-2 text-sm">No audit entries yet.</p>
        ) : (
          <ul className="space-y-1.5 text-sm">
            {station.audit.map((a) => (
              <li
                key={a.id}
                className="border-fg-3/20 flex flex-wrap items-baseline gap-3 border-b py-1.5 last:border-0"
              >
                <span className="text-fg-2 min-w-[160px] font-mono text-xs">
                  {new Date(a.created_at).toLocaleString()}
                </span>
                <span className="bg-bg-3 text-fg-1 rounded font-mono text-[10px] px-1.5 py-0.5 uppercase tracking-widest">
                  {a.decision}
                </span>
                <span className="text-fg-2 font-mono text-xs">
                  {a.admin_email}
                </span>
                {a.notes ? (
                  <span className="text-fg-1 italic text-xs">
                    “{a.notes}”
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}

function BackButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-fg-2 hover:text-fg-0 inline-flex items-center gap-2 font-mono text-xs uppercase tracking-widest"
    >
      <ArrowLeft size={14} />
      Back
    </button>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section
      className={cn(
        'border-fg-3/40 bg-bg-2/40 rounded-lg border p-5',
      )}
    >
      <h3 className="font-display text-fg-0 mb-3 text-sm font-semibold uppercase tracking-widest">
        {title}
      </h3>
      {children}
    </section>
  );
}

function InfoRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border-fg-3/20 flex items-center justify-between gap-3 border-b py-1.5 last:border-0">
      <dt className="text-fg-2 font-mono text-[10px] uppercase tracking-widest">
        {label}
      </dt>
      <dd className="text-fg-1 text-right text-sm">{children}</dd>
    </div>
  );
}
