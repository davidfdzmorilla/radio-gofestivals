'use client';

import { useEffect, useRef, useState } from 'react';
import { Loader2, Star } from 'lucide-react';
import { promoteStreamToPrimary } from '@/lib/admin/streams';
import { cn } from '@/lib/utils';

interface PromotePrimaryButtonProps {
  streamId: string;
  onPromoted: () => void | Promise<void>;
  disabled?: boolean;
}

export function PromotePrimaryButton({
  streamId,
  onPromoted,
  disabled,
}: PromotePrimaryButtonProps) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  async function handleClick() {
    if (disabled || busy) return;

    if (!confirming) {
      setConfirming(true);
      setError(null);
      timerRef.current = setTimeout(() => {
        setConfirming(false);
        timerRef.current = null;
      }, 3000);
      return;
    }

    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setBusy(true);
    try {
      await promoteStreamToPrimary(streamId);
      await onPromoted();
    } catch (err) {
      const code = err instanceof Error ? err.message : 'unknown';
      setError(code);
      setTimeout(() => setError(null), 5000);
    } finally {
      setConfirming(false);
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled || busy}
        aria-pressed={confirming}
        className={cn(
          'inline-flex items-center gap-1 rounded-md px-2 py-1 font-mono text-[10px] uppercase tracking-widest transition-colors',
          'disabled:cursor-not-allowed disabled:opacity-50',
          confirming
            ? 'bg-warm text-bg-0 hover:bg-warm/90'
            : 'border border-magenta/40 text-magenta hover:bg-magenta-soft/40',
        )}
      >
        {busy ? (
          <Loader2 size={12} className="animate-spin" />
        ) : (
          <Star size={12} />
        )}
        {busy
          ? 'Promoting…'
          : confirming
            ? 'Confirm?'
            : 'Promote to primary'}
      </button>
      {error ? (
        <span className="text-warm font-mono text-[10px]">
          {error === 'already_primary'
            ? 'Ya es primary'
            : `Error: ${error}`}
        </span>
      ) : null}
    </div>
  );
}
