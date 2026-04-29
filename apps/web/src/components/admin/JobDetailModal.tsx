'use client';

import { useEffect } from 'react';
import { X } from 'lucide-react';
import type { AdminJob, JobStatus } from '@/lib/admin/operations';
import { cn } from '@/lib/utils';

interface JobDetailModalProps {
  job: AdminJob;
  onClose: () => void;
}

const STATUS_STYLES: Record<JobStatus, string> = {
  pending: 'bg-bg-3 text-fg-1 border-fg-3/40',
  running: 'bg-cyan-soft text-cyan border-cyan/40 animate-pulse',
  success: 'bg-cyan-soft text-cyan border-cyan/40',
  failed: 'bg-magenta-soft text-warm border-magenta/40',
  timeout: 'bg-magenta-soft/60 text-warm border-magenta/40',
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
  const m = Math.floor(ms / 60_000);
  const s = Math.floor((ms % 60_000) / 1000);
  return `${m}m ${s}s`;
}

export function JobDetailModal({ job, onClose }: JobDetailModalProps) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const params = job.params_json ?? {};
  const hasParams = Object.keys(params).length > 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-bg-0/80 p-4 backdrop-blur"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="border-fg-3/40 bg-bg-2 max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-lg border shadow-sticker-lg">
        <div className="border-fg-3/40 bg-bg-2 sticky top-0 flex items-center justify-between border-b px-4 py-3">
          <h2 className="font-display text-fg-0 text-lg font-semibold">
            Job #{job.id}
            <span className="text-fg-2 ml-2 font-mono text-sm font-normal">
              {job.command}
            </span>
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-fg-2 hover:text-fg-0"
          >
            <X size={18} />
          </button>
        </div>

        <div className="space-y-4 p-4">
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <Item label="Status">
              <span
                className={cn(
                  'inline-block rounded-md border px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest',
                  STATUS_STYLES[job.status],
                )}
              >
                {job.status}
              </span>
            </Item>
            <Item label="Duration">
              <span className="font-mono text-xs">
                {formatDuration(job.started_at, job.finished_at)}
              </span>
            </Item>
            <Item label="Started">
              <span className="font-mono text-xs">
                {job.started_at
                  ? new Date(job.started_at).toLocaleString()
                  : '—'}
              </span>
            </Item>
            <Item label="Finished">
              <span className="font-mono text-xs">
                {job.finished_at
                  ? new Date(job.finished_at).toLocaleString()
                  : '—'}
              </span>
            </Item>
            <Item label="Created">
              <span className="font-mono text-xs">
                {new Date(job.created_at).toLocaleString()}
              </span>
            </Item>
            <Item label="Admin">
              <span className="font-mono text-xs">
                {job.admin_email ?? job.admin_id}
              </span>
            </Item>
          </dl>

          {hasParams ? (
            <Section title="Params">
              <pre className="border-fg-3/40 bg-bg-1 overflow-x-auto rounded-md border p-3 font-mono text-xs">
                {JSON.stringify(params, null, 2)}
              </pre>
            </Section>
          ) : null}

          {job.result_json ? (
            <Section title="Result">
              <pre className="border-fg-3/40 bg-bg-1 overflow-x-auto rounded-md border p-3 font-mono text-xs">
                {JSON.stringify(job.result_json, null, 2)}
              </pre>
            </Section>
          ) : null}

          {job.stderr_tail ? (
            <Section title="Stderr (tail)" tone="error">
              <pre className="border-magenta/40 bg-magenta-soft/40 text-warm overflow-x-auto whitespace-pre-wrap rounded-md border p-3 font-mono text-xs">
                {job.stderr_tail}
              </pre>
            </Section>
          ) : null}

          {job.status === 'pending' ? (
            <p className="text-fg-2 bg-bg-3/40 rounded-md px-3 py-2 text-sm">
              Esperando worker… (cron procesa cada minuto)
            </p>
          ) : null}
          {job.status === 'running' ? (
            <p className="text-cyan bg-cyan-soft/40 rounded-md px-3 py-2 text-sm">
              Ejecutándose…
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function Item({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-fg-2 font-mono text-[10px] uppercase tracking-widest">
        {label}
      </dt>
      <dd className="text-fg-1 mt-0.5">{children}</dd>
    </div>
  );
}

function Section({
  title,
  children,
  tone,
}: {
  title: string;
  children: React.ReactNode;
  tone?: 'error';
}) {
  return (
    <div className="space-y-1">
      <h3
        className={cn(
          'font-mono text-[10px] uppercase tracking-widest',
          tone === 'error' ? 'text-warm' : 'text-fg-2',
        )}
      >
        {title}
      </h3>
      {children}
    </div>
  );
}
