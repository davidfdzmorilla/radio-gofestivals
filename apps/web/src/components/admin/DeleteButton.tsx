'use client';

import { useEffect, useRef, useState } from 'react';
import { Loader2, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface DeleteButtonProps {
  onDelete: () => void | Promise<void>;
  disabled?: boolean;
  label?: string;
  confirmLabel?: string;
  timeoutMs?: number;
}

export function DeleteButton({
  onDelete,
  disabled,
  label = 'Delete',
  confirmLabel = 'Confirm delete?',
  timeoutMs = 3000,
}: DeleteButtonProps) {
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
      await onDelete();
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
        'inline-flex items-center gap-1 rounded-md px-2 py-1 font-mono text-[10px] uppercase tracking-widest transition-colors',
        'disabled:cursor-not-allowed disabled:opacity-50',
        confirming
          ? 'bg-magenta text-fg-0 hover:bg-magenta/90'
          : 'border border-magenta/40 text-magenta hover:bg-magenta-soft/50',
      )}
    >
      {busy ? (
        <Loader2 size={12} className="animate-spin" />
      ) : (
        <Trash2 size={12} />
      )}
      {confirming ? confirmLabel : label}
    </button>
  );
}
