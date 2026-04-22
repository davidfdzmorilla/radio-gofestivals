'use client';

import { Play, Pause } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { usePlayerStore } from '@/lib/player-store';
import type { StationSummary } from '@/lib/types';

interface Props {
  station: StationSummary;
  color: string;
}

export function PlayButton({ station, color }: Props) {
  const t = useTranslations('common');
  const current = usePlayerStore((s) => s.currentStation);
  const isPlaying = usePlayerStore((s) => s.isPlaying);
  const play = usePlayerStore((s) => s.play);
  const pause = usePlayerStore((s) => s.pause);

  const isActive = current?.id === station.id && isPlaying;

  return (
    <Button
      size="icon"
      aria-label={isActive ? t('pause') : t('play')}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        if (isActive) pause();
        else play(station);
      }}
      className="shrink-0 text-white"
      style={{ backgroundColor: color }}
    >
      {isActive ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5 translate-x-0.5" />}
    </Button>
  );
}
