'use client';

import { useState } from 'react';
import { Play, Pause } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { cn } from '@/lib/utils';
import { usePlayerStore } from '@/lib/player-store';
import type { StationSummary } from '@/lib/types';

interface Props {
  station: StationSummary;
  color: string;
  size?: 'sm' | 'md' | 'lg';
}

const sizeMap = {
  sm: 'h-9 w-9',
  md: 'h-11 w-11',
  lg: 'h-16 w-16',
} as const;

const iconMap = {
  sm: 'h-4 w-4',
  md: 'h-5 w-5',
  lg: 'h-7 w-7',
} as const;

export function PlayButton({ station, color, size = 'md' }: Props) {
  const t = useTranslations('common');
  const current = usePlayerStore((s) => s.currentStation);
  const isPlaying = usePlayerStore((s) => s.isPlaying);
  const play = usePlayerStore((s) => s.play);
  const pause = usePlayerStore((s) => s.pause);

  const [pulseKey, setPulseKey] = useState(0);
  const isActive = current?.id === station.id && isPlaying;

  return (
    <button
      key={pulseKey}
      aria-label={isActive ? t('pause') : t('play')}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        if (isActive) pause();
        else {
          play(station);
          setPulseKey((k) => k + 1);
        }
      }}
      style={{ backgroundColor: color }}
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-full text-bg-0 shadow-sticker ring-0 transition-transform duration-200',
        'rotate-1 hover:-rotate-1 hover:-translate-y-0.5',
        'animate-pulse-play',
        sizeMap[size],
      )}
    >
      {isActive ? (
        <Pause className={cn(iconMap[size], 'fill-bg-0')} />
      ) : (
        <Play className={cn(iconMap[size], 'translate-x-0.5 fill-bg-0')} />
      )}
    </button>
  );
}
