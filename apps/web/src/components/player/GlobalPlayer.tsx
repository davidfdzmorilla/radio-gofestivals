'use client';

import { useEffect, useRef } from 'react';
import { Play, Pause, X, Volume2 } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { cn, initials } from '@/lib/utils';
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
  const error = usePlayerStore((s) => s.error);
  const pause = usePlayerStore((s) => s.pause);
  const stop = usePlayerStore((s) => s.stop);
  const toggle = usePlayerStore((s) => s.toggle);
  const setBuffering = usePlayerStore((s) => s.setBuffering);
  const setVolume = usePlayerStore((s) => s.setVolume);
  const tryNextFallback = usePlayerStore((s) => s.tryNextFallback);
  const retry = usePlayerStore((s) => s.retry);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.volume = volume;
  }, [volume]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    if (!station) {
      audio.pause();
      audio.removeAttribute('src');
      audio.load();
      return;
    }

    // Prefer the explicit stream URL on the station summary so the quality
    // selector can switch variants without going through the slug-based
    // 302 redirect endpoint. Fallback to the API redirect for any caller
    // that still passes a station without primary_stream populated.
    const nextSrc =
      station.primary_stream?.url ??
      `${API_BASE}/api/v1/stations/${station.slug}/stream`;
    const srcChanged = audio.src !== nextSrc;
    let cancelled = false;

    const apply = async () => {
      if (srcChanged) {
        // pause-reset-load BEFORE assigning new src — switching src on a
        // playing element rejects the in-flight play() with AbortError and
        // leaves the audio in a frozen state.
        audio.pause();
        audio.src = nextSrc;
        audio.load();
      }
      if (!isPlaying) {
        audio.pause();
        return;
      }
      try {
        await audio.play();
      } catch (err) {
        // AbortError is the expected outcome when the user switches stations
        // mid-play (next effect run interrupts this one). Don't flip state.
        if (err instanceof DOMException && err.name === 'AbortError') return;
        if (!cancelled) pause();
      }
    };

    void apply();
    return () => {
      cancelled = true;
    };
  }, [station, isPlaying, pause]);

  if (!station) return null;

  return (
    <div
      className={cn(
        'fixed inset-x-0 bottom-0 z-50 border-t-2 border-wave/50 bg-bg-0/95 backdrop-blur-lg animate-player',
      )}
    >
      <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
        <div
          aria-hidden
          className="hidden h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-wave font-display text-lg font-bold text-bg-0 shadow-sticker-sm sm:flex"
        >
          {initials(station.name)}
        </div>
        <button
          type="button"
          aria-label={isPlaying ? tCommon('pause') : tCommon('play')}
          onClick={() => toggle()}
          className="inline-flex h-11 w-11 shrink-0 rotate-1 items-center justify-center rounded-full bg-wave text-bg-0 shadow-sticker transition-transform duration-200 hover:-rotate-1 hover:-translate-y-0.5"
        >
          {isPlaying ? (
            <Pause className="h-5 w-5 fill-bg-0" />
          ) : (
            <Play className="h-5 w-5 translate-x-0.5 fill-bg-0" />
          )}
        </button>
        <div className="min-w-0 flex-1">
          <p className="truncate font-mono text-[11px] uppercase tracking-wide text-fg-2">
            {station.name}
          </p>
          {error ? (
            <p className="flex items-center gap-2 font-display text-sm italic text-fg-2">
              <span>{t('streamUnavailable')}</span>
              <button
                type="button"
                onClick={() => retry()}
                className="rounded-full border border-fg-3 bg-bg-2 px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-fg-1 transition-colors hover:border-magenta/60 hover:text-fg-0"
              >
                {t('retry')}
              </button>
            </p>
          ) : isBuffering && !isPlaying ? (
            <p className="font-display text-sm italic text-fg-2">{t('buffering')}</p>
          ) : (
            <NowPlaying slug={station.slug} />
          )}
        </div>
        <label className="hidden items-center gap-2 text-fg-2 sm:flex">
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
        onError={() => {
          // Conservative trigger: only audio.onerror — no onstalled, no
          // timeout. Covers network errors, decode errors, 404s and
          // content-type mismatches. tryNextFallback returns false when
          // every active stream has been tried; in that case it has
          // already set error='streamUnavailable' and pause()d.
          if (!tryNextFallback()) {
            pause();
          }
        }}
      />
    </div>
  );
}
