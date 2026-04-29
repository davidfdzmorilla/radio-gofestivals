'use client';

import { useEffect, useState, type FormEvent } from 'react';
import { Loader2, Play, X } from 'lucide-react';
import { runCommand, type AdminJob } from '@/lib/admin/operations';
import { cn } from '@/lib/utils';

interface AutoCurateModalProps {
  adminEmail: string;
  onClose: () => void;
  onJobCreated: (job: AdminJob) => void;
}

export function AutoCurateModal({
  adminEmail,
  onClose,
  onJobCreated,
}: AutoCurateModalProps) {
  const [minQuality, setMinQuality] = useState(70);
  const [limit, setLimit] = useState(50);
  const [country, setCountry] = useState('');
  const [dryRun, setDryRun] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !submitting) onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose, submitting]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);

    try {
      const job = await runCommand('auto_curate', {
        admin_email: adminEmail,
        min_quality: minQuality,
        limit,
        country: country ? country : null,
        dry_run: dryRun,
      });
      onJobCreated(job);
    } catch (err) {
      const code = err instanceof Error ? err.message : 'unknown';
      if (code.startsWith('invalid_params:')) {
        setError(`Validación falló: ${code.replace('invalid_params:', '')}`);
      } else if (code === 'command_not_allowed') {
        setError('El comando auto_curate no está permitido en este entorno.');
      } else {
        setError(`Error: ${code}`);
      }
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-bg-0/80 p-4 backdrop-blur"
      onClick={(e) => {
        if (e.target === e.currentTarget && !submitting) onClose();
      }}
    >
      <div className="border-fg-3/40 bg-bg-2 max-h-[90vh] w-full max-w-md overflow-y-auto rounded-lg border shadow-sticker-lg">
        <div className="border-fg-3/40 flex items-center justify-between border-b px-4 py-3">
          <h2 className="font-display text-fg-0 text-lg font-semibold">
            Auto-curate top stations
          </h2>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            aria-label="Close"
            className="text-fg-2 hover:text-fg-0 disabled:opacity-50"
          >
            <X size={18} />
          </button>
        </div>

        <p className="text-fg-2 px-4 pt-3 text-sm">
          Promueve stations <code className="font-mono text-xs">pending</code>{' '}
          con quality_score &gt;= threshold a curated. Crea entries en
          curation_log con decision=&apos;approve&apos;.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4 p-4">
          <Field label="Admin email">
            <input
              type="text"
              value={adminEmail}
              readOnly
              className="border-fg-3 bg-bg-1/60 text-fg-2 w-full cursor-not-allowed rounded-md border px-3 py-2 font-mono text-sm"
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Min quality (0-100)" htmlFor="ac-min-q">
              <input
                id="ac-min-q"
                type="number"
                min={0}
                max={100}
                value={minQuality}
                onChange={(e) => setMinQuality(Number(e.target.value))}
                disabled={submitting}
                className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta w-full rounded-md border px-3 py-2 text-sm focus:outline-none disabled:opacity-50"
              />
            </Field>
            <Field label="Limit (1-500)" htmlFor="ac-limit">
              <input
                id="ac-limit"
                type="number"
                min={1}
                max={500}
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                disabled={submitting}
                className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta w-full rounded-md border px-3 py-2 text-sm focus:outline-none disabled:opacity-50"
              />
            </Field>
          </div>

          <Field
            label="Country"
            htmlFor="ac-country"
            hint="(opcional, ISO 2 letras)"
          >
            <input
              id="ac-country"
              type="text"
              maxLength={2}
              placeholder="ES, IT, FR…"
              value={country}
              onChange={(e) => setCountry(e.target.value.toUpperCase())}
              disabled={submitting}
              className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta w-full rounded-md border px-3 py-2 font-mono text-sm uppercase focus:outline-none disabled:opacity-50"
            />
          </Field>

          <div
            className={cn(
              'rounded-md border p-3 transition-colors',
              dryRun
                ? 'border-cyan-soft bg-cyan-soft/30'
                : 'border-magenta/40 bg-magenta-soft/40',
            )}
          >
            <label className="flex cursor-pointer items-start gap-2">
              <input
                type="checkbox"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
                disabled={submitting}
                className="accent-magenta mt-0.5 h-4 w-4"
              />
              <div className="text-sm">
                <div className="text-fg-0 font-medium">
                  {dryRun
                    ? '✓ Dry run (modo seguro)'
                    : '⚠ Modo real (modifica datos)'}
                </div>
                <div className="text-fg-2 mt-0.5 text-xs">
                  {dryRun
                    ? 'Simula la operación sin tocar la base de datos.'
                    : 'Promueve realmente las stations a curated y crea audit entries.'}
                </div>
              </div>
            </label>
          </div>

          {error ? (
            <div
              role="alert"
              className="bg-magenta-soft text-warm rounded-md px-3 py-2 text-sm"
            >
              {error}
            </div>
          ) : null}

          <div className="border-fg-3/40 flex items-center justify-end gap-2 border-t pt-3">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="border-fg-3 text-fg-1 hover:border-magenta hover:text-fg-0 rounded-md border px-3 py-1.5 font-mono text-xs uppercase tracking-widest transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="bg-wave text-fg-0 shadow-sticker hover:bg-magenta hover:shadow-sticker-magenta inline-flex items-center gap-2 rounded-md px-3 py-1.5 font-display text-sm font-medium transition-all disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Play size={14} />
              )}
              {submitting ? 'Encolando…' : 'Run auto-curate'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Field({
  label,
  htmlFor,
  hint,
  children,
}: {
  label: string;
  htmlFor?: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label
        htmlFor={htmlFor}
        className="text-fg-2 block font-mono text-[10px] uppercase tracking-widest"
      >
        {label}
        {hint ? (
          <span className="text-fg-3 ml-1 normal-case">{hint}</span>
        ) : null}
      </label>
      {children}
    </div>
  );
}
