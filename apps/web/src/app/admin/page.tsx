'use client';

import { useEffect, useState } from 'react';
import { Loader2, RefreshCw } from 'lucide-react';
import {
  type DashboardStats,
  getDashboardStats,
} from '@/lib/admin/dashboard';
import { ActivityFeed } from '@/components/admin/ActivityFeed';
import { BarChart } from '@/components/admin/BarChart';
import { KpiCard } from '@/components/admin/KpiCard';
import { cn } from '@/lib/utils';

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load(isRefresh = false) {
    if (isRefresh) setRefreshing(true);
    setError(null);
    try {
      const data = await getDashboardStats();
      setStats(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'unknown_error');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  if (loading) {
    return (
      <div className="text-fg-2 flex items-center justify-center gap-2 py-12 font-mono text-xs uppercase tracking-widest">
        <Loader2 size={16} className="animate-spin" />
        Loading…
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="space-y-3">
        <div
          role="alert"
          className="bg-magenta-soft text-warm rounded-md px-3 py-2 text-sm"
        >
          {error ?? 'No data'}
        </div>
        <button
          type="button"
          onClick={() => void load(true)}
          className="border-fg-3 text-fg-1 hover:border-magenta hover:text-fg-0 inline-flex items-center gap-2 rounded-md border px-3 py-1.5 font-mono text-xs uppercase tracking-widest transition-colors"
        >
          <RefreshCw size={14} />
          Retry
        </button>
      </div>
    );
  }

  const brokenAccent = stats.kpis.stations_broken > 50 ? 'warning' : 'default';

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-fg-0 text-2xl font-bold">
            Dashboard
          </h2>
          <p className="text-fg-2 mt-1 font-mono text-xs uppercase tracking-widest">
            Snapshot del estado del producto
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load(true)}
          disabled={refreshing}
          className="border-fg-3 text-fg-1 hover:border-magenta hover:text-fg-0 inline-flex items-center gap-2 rounded-md border px-3 py-1.5 font-mono text-xs uppercase tracking-widest transition-colors disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw
            size={14}
            className={cn(refreshing && 'animate-spin')}
          />
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard
          label="Active stations"
          value={stats.kpis.stations_active}
          sublabel="status=active"
        />
        <KpiCard
          label="Curated"
          value={stats.kpis.stations_curated}
          sublabel="active + curated=true"
          accent="success"
        />
        <KpiCard
          label="Broken"
          value={stats.kpis.stations_broken}
          sublabel="needs attention"
          accent={brokenAccent}
        />
        <KpiCard
          label="Avg quality"
          value={stats.kpis.avg_quality_active.toFixed(1)}
          sublabel="0–100, active stations"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Section
          title="Quality distribution"
          subtitle="Active stations by quality_score bucket"
        >
          <BarChart
            data={stats.quality_distribution.map((b) => ({
              label: b.bucket,
              value: b.count,
            }))}
          />
        </Section>

        <Section
          title="Top genres curated"
          subtitle="Curated active stations per genre"
        >
          <BarChart
            data={stats.top_genres_curated.map((g) => ({
              label: g.name,
              value: g.count,
            }))}
            maxBars={10}
          />
        </Section>

        <Section
          title="Top countries"
          subtitle="Active stations by country_code"
        >
          <BarChart
            data={stats.top_countries.map((c) => ({
              label: c.country_code,
              value: c.count,
            }))}
            maxBars={10}
          />
        </Section>

        <Section
          title="Recent activity"
          subtitle="Last 20 entries from curation_log"
        >
          <div className="max-h-[400px] overflow-y-auto">
            <ActivityFeed entries={stats.recent_activity} />
          </div>
        </Section>
      </div>
    </div>
  );
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border-fg-3/40 bg-bg-2/40 overflow-hidden rounded-lg border">
      <header className="border-fg-3/40 bg-bg-3/30 border-b px-4 py-2">
        <h3 className="font-mono text-[10px] uppercase tracking-widest text-fg-2">
          {title}
        </h3>
        {subtitle ? (
          <p className="text-fg-3 mt-0.5 text-[10px]">{subtitle}</p>
        ) : null}
      </header>
      <div className="p-4">{children}</div>
    </section>
  );
}
