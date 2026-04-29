'use client';

import { useEffect, useRef, useState } from 'react';
import { Loader2, Play } from 'lucide-react';
import { cn } from '@/lib/utils';

interface RunButtonProps {
  onRun: () => void | Promise<void>;
  disabled?: boolean;
  label?: string;
  confirmLabel?: string;
  busyLabel?: string;
  timeoutMs?: number;
}

export function RunButton({
  onRun,
  disabled,
  label = 'Run',
  confirmLabel = 'Confirm?',
  busyLabel = 'Running…',
  timeoutMs = 3000,
}: RunButtonProps) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
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
      timerRef.current = setTimeout(() => {
        setConfirming(false);
        timerRef.current = null;
      }, timeoutMs);
      return;
    }

    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setBusy(true);
    try {
      await onRun();
    } finally {
      setConfirming(false);
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={disabled || busy}
      aria-pressed={confirming}
      className={cn(
        'inline-flex items-center gap-2 rounded-md px-3 py-1.5 font-display text-sm font-medium transition-all shadow-sticker',
        'disabled:cursor-not-allowed disabled:opacity-50',
        busy && 'bg-wave/60 text-fg-0',
        !busy && confirming && 'bg-warm text-bg-0 hover:bg-warm/90',
        !busy && !confirming && 'bg-wave text-fg-0 hover:bg-magenta hover:shadow-sticker-magenta',
      )}
    >
      {busy ? (
        <Loader2 size={14} className="animate-spin" />
      ) : (
        <Play size={14} />
      )}
      {busy ? busyLabel : confirming ? confirmLabel : label}
    </button>
  );
}
