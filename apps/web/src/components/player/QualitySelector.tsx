'use client';

import { useTranslations } from 'next-intl';
import { cn } from '@/lib/utils';
import type { StationStreamRef } from '@/lib/types';

interface Props {
  streams: StationStreamRef[];
  activeStreamId: string;
  onSelect: (stream: StationStreamRef) => void;
}

function formatLabel(stream: StationStreamRef): string {
  const codec = stream.codec ?? stream.format ?? '?';
  const bitrate = stream.bitrate != null ? String(stream.bitrate) : '—';
  return `${bitrate} ${codec}`;
}

export function QualitySelector({ streams, activeStreamId, onSelect }: Props) {
  const t = useTranslations('player');
  if (streams.length <= 1) return null;

  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label={t('quality')}>
      <span className="font-mono text-[11px] uppercase tracking-widest text-fg-2">
        {t('quality')}
      </span>
      {streams.map((stream) => {
        const isActive = stream.id === activeStreamId;
        return (
          <button
            key={stream.id}
            type="button"
            aria-pressed={isActive}
            onClick={() => onSelect(stream)}
            className={cn(
              'rounded-full border px-3 py-1 font-mono text-[11px] uppercase tracking-widest transition-all',
              'hover:-translate-y-0.5 hover:shadow-sticker-sm',
              isActive
                ? '-rotate-1 border-magenta/60 bg-magenta-soft text-fg-0 shadow-sticker-sm'
                : 'border-fg-3 bg-bg-2 text-fg-2 hover:border-fg-2 hover:text-fg-1',
            )}
          >
            {formatLabel(stream)}
          </button>
        );
      })}
    </div>
  );
}
