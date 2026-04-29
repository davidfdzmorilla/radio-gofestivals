'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Loader2, Settings2 } from 'lucide-react';
import {
  type AdminJob,
  type CommandCatalogEntry,
  type JobStatus,
  getCatalog,
  listJobs,
  runCommand,
} from '@/lib/admin/operations';
import { type AdminMe, getMe } from '@/lib/admin/auth';
import { AutoCurateModal } from '@/components/admin/AutoCurateModal';
import { JobDetailModal } from '@/components/admin/JobDetailModal';
import { RunButton } from '@/components/admin/RunButton';
import { cn } from '@/lib/utils';

const ACTIVE_POLL_MS = 5_000;
const IDLE_POLL_MS = 60_000;
const STATUS_OPTIONS: { value: JobStatus | ''; label: string }[] = [
  { value: '', label: 'All statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'running', label: 'Running' },
  { value: 'success', label: 'Success' },
  { value: 'failed', label: 'Failed' },
  { value: 'timeout', label: 'Timeout' },
];

const STATUS_BADGE: Record<JobStatus, string> = {
  pending: 'bg-bg-3 text-fg-1',
  running: 'bg-cyan-soft text-cyan animate-pulse',
  success: 'bg-cyan-soft text-cyan',
  failed: 'bg-magenta-soft text-warm',
  timeout: 'bg-magenta-soft/60 text-warm',
};

function formatDuration(
  started: string | null,
  finished: string | null,
): string {
  if (!started) return '—';
  if (!finished) return '…';
  const ms = new Date(finished).getTime() - new Date(started).getTime();
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60_000)}m ${Math.floor((ms % 60_000) / 1000)}s`;
}

export default function OperationsPage() {
  const [catalog, setCatalog] = useState<CommandCatalogEntry[]>([]);
  const [jobs, setJobs] = useState<AdminJob[]>([]);
  const [admin, setAdmin] = useState<AdminMe | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAutoCurate, setShowAutoCurate] = useState(false);
  const [selectedJob, setSelectedJob] = useState<AdminJob | null>(null);
  const [statusFilter, setStatusFilter] = useState<JobStatus | ''>('');

  const isVisibleRef = useRef(true);

  const fetchJobs = useCallback(async () => {
    try {
      const result = await listJobs({
        size: 50,
        status: statusFilter || undefined,
      });
      setJobs(result.items);
      // If the user has an open detail modal, refresh it from the new list.
      setSelectedJob((prev) => {
        if (!prev) return null;
        const updated = result.items.find((j) => j.id === prev.id);
        return updated ?? prev;
      });
    } catch (err) {
      console.error('list_jobs_failed', err);
    }
  }, [statusFilter]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getCatalog(), getMe(), listJobs({ size: 50 })])
      .then(([cat, me, page]) => {
        if (cancelled) return;
        setCatalog(cat);
        setAdmin(me);
        setJobs(page.items);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'unknown_error');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Refetch whenever the status filter changes (after initial load).
  useEffect(() => {
    if (loading) return;
    fetchJobs();
  }, [statusFilter, fetchJobs, loading]);

  // Page Visibility — pause polling when the tab is hidden.
  useEffect(() => {
    const handler = () => {
      isVisibleRef.current = !document.hidden;
    };
    document.addEventListener('visibilitychange', handler);
    return () => document.removeEventListener('visibilitychange', handler);
  }, []);

  // Adaptive polling: fast while there are pending/running jobs, slow otherwise.
  useEffect(() => {
    const hasActive = jobs.some(
      (j) => j.status === 'pending' || j.status === 'running',
    );
    const interval = hasActive ? ACTIVE_POLL_MS : IDLE_POLL_MS;
    const timer = window.setInterval(() => {
      if (isVisibleRef.current) fetchJobs();
    }, interval);
    return () => window.clearInterval(timer);
  }, [jobs, fetchJobs]);

  async function handleRun(command: string) {
    setError(null);
    try {
      await runCommand(command);
      await fetchJobs();
    } catch (err) {
      const code = err instanceof Error ? err.message : 'unknown';
      setError(`Error encolando ${command}: ${code}`);
      window.setTimeout(() => setError(null), 5_000);
    }
  }

  function handleAutoCurateCreated(job: AdminJob) {
    setShowAutoCurate(false);
    setJobs((prev) => [job, ...prev]);
    void fetchJobs();
  }

  if (loading) {
    return (
      <div className="text-fg-2 flex items-center justify-center gap-2 py-12 font-mono text-xs uppercase tracking-widest">
        <Loader2 size={16} className="animate-spin" />
        Loading…
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h2 className="font-display text-fg-0 text-2xl font-bold">
          Operations
        </h2>
        <p className="text-fg-2 mt-1 font-mono text-xs uppercase tracking-widest">
          Worker procesa jobs cada minuto
        </p>
      </div>

      {error ? (
        <div
          role="alert"
          className="bg-magenta-soft text-warm rounded-md px-3 py-2 text-sm"
        >
          {error}
        </div>
      ) : null}

      <section className="border-fg-3/40 bg-bg-2/40 overflow-hidden rounded-lg border">
        <div className="border-fg-3/40 bg-bg-3/30 border-b px-4 py-2">
          <h3 className="font-mono text-[10px] uppercase tracking-widest text-fg-2">
            Run command
          </h3>
        </div>
        <ul className="divide-fg-3/30 divide-y">
          {catalog.map((cmd) => {
            const isAutoCurate = cmd.command === 'auto_curate';
            return (
              <li
                key={cmd.command}
                className="flex flex-wrap items-start gap-4 px-4 py-3"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline gap-2">
                    <span className="text-fg-0 font-medium">{cmd.label}</span>
                    <span className="text-fg-2 font-mono text-xs">
                      {cmd.command}
                    </span>
                    {isAutoCurate ? (
                      <Settings2 size={12} className="text-magenta" />
                    ) : null}
                  </div>
                  <p className="text-fg-2 mt-0.5 text-sm">{cmd.description}</p>
                  <p className="text-fg-3 mt-0.5 font-mono text-[10px] uppercase tracking-widest">
                    Timeout {cmd.timeout}s
                  </p>
                </div>
                {isAutoCurate ? (
                  <button
                    type="button"
                    onClick={() => setShowAutoCurate(true)}
                    className="bg-wave text-fg-0 shadow-sticker hover:bg-magenta hover:shadow-sticker-magenta inline-flex items-center gap-1 rounded-md px-3 py-1.5 font-display text-sm font-medium transition-all"
                  >
                    Configure & Run
                  </button>
                ) : (
                  <RunButton onRun={() => handleRun(cmd.command)} />
                )}
              </li>
            );
          })}
        </ul>
      </section>

      <section className="border-fg-3/40 bg-bg-2/40 overflow-hidden rounded-lg border">
        <div className="border-fg-3/40 bg-bg-3/30 flex items-center justify-between gap-3 border-b px-4 py-2">
          <h3 className="font-mono text-[10px] uppercase tracking-widest text-fg-2">
            Recent jobs ({jobs.length})
          </h3>
          <select
            value={statusFilter}
            onChange={(e) =>
              setStatusFilter(e.target.value as JobStatus | '')
            }
            className="border-fg-3 bg-bg-1 text-fg-1 rounded-md border px-2 py-1 text-xs focus:outline-none"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {jobs.length === 0 ? (
          <p className="text-fg-2 py-10 text-center text-sm">
            No jobs yet. Run a command above.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-bg-3/30 text-fg-2 font-mono text-[10px] uppercase tracking-widest">
                <tr>
                  <th className="px-4 py-2 text-left">ID</th>
                  <th className="px-4 py-2 text-left">Command</th>
                  <th className="px-4 py-2 text-left">Status</th>
                  <th className="px-4 py-2 text-left">Started</th>
                  <th className="px-4 py-2 text-left">Duration</th>
                </tr>
              </thead>
              <tbody className="divide-fg-3/30 divide-y">
                {jobs.map((job) => (
                  <tr
                    key={job.id}
                    onClick={() => setSelectedJob(job)}
                    className="hover:bg-bg-3/40 cursor-pointer transition-colors"
                  >
                    <td className="text-fg-2 px-4 py-2 font-mono text-xs">
                      {job.id}
                    </td>
                    <td className="text-fg-1 px-4 py-2 font-mono text-xs">
                      {job.command}
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={cn(
                          'inline-block rounded-md px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest',
                          STATUS_BADGE[job.status],
                        )}
                      >
                        {job.status}
                      </span>
                    </td>
                    <td className="text-fg-2 px-4 py-2 font-mono text-xs">
                      {job.started_at
                        ? new Date(job.started_at).toLocaleTimeString()
                        : '—'}
                    </td>
                    <td className="text-fg-1 px-4 py-2 font-mono text-xs">
                      {formatDuration(job.started_at, job.finished_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {showAutoCurate && admin ? (
        <AutoCurateModal
          adminEmail={admin.email}
          onClose={() => setShowAutoCurate(false)}
          onJobCreated={handleAutoCurateCreated}
        />
      ) : null}
      {selectedJob ? (
        <JobDetailModal
          job={selectedJob}
          onClose={() => setSelectedJob(null)}
        />
      ) : null}
    </div>
  );
}
