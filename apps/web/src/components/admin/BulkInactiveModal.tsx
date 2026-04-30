'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, Loader2, X } from 'lucide-react';
import { bulkStatusChange } from '@/lib/admin/streams';

interface BulkInactiveModalProps {
  selectedIds: string[];
  selectedNames: string[];
  onClose: () => void;
  onCompleted: (affected: number, skipped: number) => void;
}

export function BulkInactiveModal({
  selectedIds,
  selectedNames,
  onClose,
  onCompleted,
}: BulkInactiveModalProps) {
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !submitting) onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose, submitting]);

  async function handleSubmit() {
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await bulkStatusChange(
        selectedIds,
        'inactive',
        reason ? reason : undefined,
      );
      onCompleted(result.affected, result.skipped);
    } catch (err) {
      const code = err instanceof Error ? err.message : 'unknown';
      if (code.startsWith('validation_failed:')) {
        setError(`Validación falló: ${code.replace('validation_failed:', '')}`);
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
          <div className="flex items-center gap-2">
            <AlertTriangle size={16} className="text-warm" />
            <h2 className="font-display text-fg-0 text-lg font-semibold">
              Mark as inactive
            </h2>
          </div>
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

        <div className="space-y-4 p-4">
          <p className="text-fg-1 text-sm">
            Estás a punto de marcar{' '}
            <strong className="text-fg-0">
              {selectedIds.length}{' '}
              {selectedIds.length === 1 ? 'station' : 'stations'}
            </strong>{' '}
            como inactive. Esto las ocultará del frontend público.
          </p>

          <div className="border-fg-3/40 bg-bg-1 max-h-32 overflow-y-auto rounded-md border p-3">
            <ul className="space-y-0.5 font-mono text-xs">
              {selectedNames.slice(0, 10).map((name, i) => (
                <li key={`${name}-${i}`} className="text-fg-1">
                  · {name}
                </li>
              ))}
              {selectedNames.length > 10 ? (
                <li className="text-fg-2 italic">
                  … y {selectedNames.length - 10} más
                </li>
              ) : null}
            </ul>
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="bulk-reason"
              className="text-fg-2 block font-mono text-[10px] uppercase tracking-widest"
            >
              Reason{' '}
              <span className="text-fg-3 normal-case">
                (opcional, se guarda en audit)
              </span>
            </label>
            <input
              id="bulk-reason"
              type="text"
              maxLength={200}
              placeholder="ej. cleanup chronic broken"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              disabled={submitting}
              className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta w-full rounded-md border px-3 py-2 text-sm focus:outline-none disabled:opacity-50"
            />
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
              type="button"
              onClick={handleSubmit}
              disabled={submitting}
              className="bg-warm text-bg-0 hover:bg-warm/90 inline-flex items-center gap-2 rounded-md px-3 py-1.5 font-display text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? (
                <Loader2 size={14} className="animate-spin" />
              ) : null}
              {submitting
                ? 'Marking…'
                : `Mark ${selectedIds.length} as inactive`}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
