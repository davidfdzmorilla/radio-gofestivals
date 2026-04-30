'use client';

import { X } from 'lucide-react';

interface BulkActionBarProps {
  count: number;
  actionLabel: string;
  onAction: () => void;
  onCancel: () => void;
}

export function BulkActionBar({
  count,
  actionLabel,
  onAction,
  onCancel,
}: BulkActionBarProps) {
  return (
    <div
      role="region"
      aria-label="Bulk action bar"
      className="border-magenta bg-bg-2 shadow-sticker-lg fixed bottom-4 left-1/2 z-40 flex -translate-x-1/2 items-center gap-3 rounded-lg border-2 px-4 py-3"
    >
      <span className="text-fg-0 font-mono text-xs uppercase tracking-widest">
        {count} {count === 1 ? 'station' : 'stations'} selected
      </span>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onAction}
          className="bg-warm text-bg-0 hover:bg-warm/90 inline-flex items-center gap-1 rounded-md px-3 py-1.5 font-display text-sm font-medium transition-colors"
        >
          {actionLabel}
        </button>
        <button
          type="button"
          onClick={onCancel}
          aria-label="Cancel selection"
          className="text-fg-2 hover:text-fg-0 transition-colors"
        >
          <X size={18} />
        </button>
      </div>
    </div>
  );
}
