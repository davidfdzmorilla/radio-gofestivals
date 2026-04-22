'use client';

import { useEffect, useRef } from 'react';
import { Play, Pause, X, Volume2 } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { usePlayerStore } from '@/lib/player-store';
import { NowPlaying } from './NowPlaying';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export function GlobalPlayer() {
  const t = useTranslations('player');
  const tCommon = useTranslations('common');
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const station = usePlayerStore((s) => s.currentStation);
  const isPlaying = usePlayerStore((s) => s.isPlaying);
  const isBuffering = usePlayerStore((s) => s.isBuffering);
  const volume = usePlayerStore((s) => s.volume);
  const pause = usePlayerStore((s) => s.pause);
  const stop = usePlayerStore((s) => s.stop);
  const toggle = usePlayerStore((s) => s.toggle);
  const setBuffering = usePlayerStore((s) => s.setBuffering);
  const setVolume = usePlayerStore((s) => s.setVolume);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.volume = volume;
  }, [volume]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !station) return;
    audio.src = `${API_BASE}/api/v1/stations/${station.slug}/stream`;
    audio.load();
  }, [station]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (isPlaying) {
      const p = audio.play();
      if (p !== undefined) {
        p.catch(() => pause());
      }
    } else {
      audio.pause();
    }
  }, [isPlaying, pause]);

  if (!station) return null;

  return (
    <div className="fixed inset-x-0 bottom-0 z-50 border-t border-white/10 bg-ink/95 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
        <Button
          variant="default"
          size="icon"
          aria-label={isPlaying ? tCommon('pause') : tCommon('play')}
          onClick={() => toggle()}
        >
          {isPlaying ? (
            <Pause className="h-5 w-5" />
          ) : (
            <Play className="h-5 w-5 translate-x-0.5" />
          )}
        </Button>
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs text-white/60">{station.name}</p>
          {isBuffering && !isPlaying ? (
            <p className="text-sm text-white/40">{t('buffering')}</p>
          ) : (
            <NowPlaying slug={station.slug} />
          )}
        </div>
        <label className="hidden items-center gap-2 text-white/50 sm:flex">
          <Volume2 className="h-4 w-4" />
          <input
            aria-label="Volume"
            type="range"
            min={0}
            max={1}
            step={0.01}
            value={volume}
            onChange={(e) => setVolume(parseFloat(e.target.value))}
            className="h-1 w-24 accent-wave"
          />
        </label>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Close"
          onClick={() => {
            if (audioRef.current) audioRef.current.pause();
            stop();
          }}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
      <audio
        ref={audioRef}
        preload="none"
        onWaiting={() => setBuffering(true)}
        onPlaying={() => setBuffering(false)}
        onError={() => pause()}
      />
    </div>
  );
}
