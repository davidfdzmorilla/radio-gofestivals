'use client';

import { useEffect, useRef, useState, type RefObject } from 'react';
import { cn } from '@/lib/utils';

interface SpectrumAnalyzerProps {
  audioRef: RefObject<HTMLAudioElement | null>;
  isPlaying: boolean;
  // Only true when the current stream sends CORS (cors_ok from the
  // health-check). Tapping a no-CORS element via Web Audio silences it, so
  // for those we never touch the element and animate decoratively instead.
  realSpectrum: boolean;
  barCount?: number;
  className?: string;
}

type Mode = 'idle' | 'real' | 'decorative';

const FRAME_INTERVAL_MS = 90;
const SILENCE_FRAMES_TO_DECORATIVE = 60;

export function groupBars(dataArray: Uint8Array, targetCount: number): number[] {
  if (targetCount <= 0) return [];
  const groupSize = Math.max(1, Math.floor(dataArray.length / targetCount));
  const groups: number[] = [];
  for (let i = 0; i < targetCount; i++) {
    const start = i * groupSize;
    const end = Math.min(start + groupSize, dataArray.length);
    const slice = dataArray.slice(start, end);
    const sum = slice.reduce((a, b) => a + b, 0);
    groups.push(slice.length > 0 ? sum / slice.length / 255 : 0);
  }
  return groups;
}

function decorativeBars(count: number, tick: number): number[] {
  // Deterministic wave (no Math.random → stable SSR/tests, reads as a VU
  // meter). Used when there is no real signal to tap.
  return Array.from({ length: count }, (_, i) => {
    const phase = Math.sin((tick + i * 1.7) / 2.2);
    return 0.25 + ((phase + 1) / 2) * 0.7;
  });
}

export function SpectrumAnalyzer({
  audioRef,
  isPlaying,
  realSpectrum,
  barCount = 10,
  className,
}: SpectrumAnalyzerProps) {
  const [bars, setBars] = useState<number[]>(() => Array(barCount).fill(0.15));
  const [mode, setMode] = useState<Mode>('idle');

  const ctxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  // Which <audio> element the current source node was created from. The
  // element remounts when crossing the CORS boundary, so on change we must
  // tear down the old source and tap the new one (createMediaElementSource
  // can be called only once per element).
  const tappedElRef = useRef<HTMLAudioElement | null>(null);
  const frameRef = useRef<number | null>(null);

  // Wire (or skip) the Web Audio tap.
  useEffect(() => {
    if (!isPlaying) {
      setMode('idle');
      return;
    }
    if (!realSpectrum) {
      // Never touch a no-CORS element: tapping it would silence playback.
      setMode('decorative');
      return;
    }
    const el = audioRef.current;
    if (!el) return;

    // Same element already tapped (reused across CORS stations): keep it,
    // just make sure the context is running.
    if (ctxRef.current && tappedElRef.current === el && analyserRef.current) {
      if (ctxRef.current.state === 'suspended') {
        ctxRef.current.resume().catch(() => {});
      }
      setMode('real');
      return;
    }

    try {
      const Ctor =
        window.AudioContext ??
        (window as unknown as { webkitAudioContext?: typeof AudioContext })
          .webkitAudioContext;
      if (!Ctor) {
        setMode('decorative');
        return;
      }
      // New element (boundary remount): drop the previous source.
      if (sourceRef.current) {
        try {
          sourceRef.current.disconnect();
        } catch {
          // ignore
        }
        sourceRef.current = null;
      }
      const ctx = ctxRef.current ?? new Ctor();
      ctxRef.current = ctx;
      if (ctx.state === 'suspended') ctx.resume().catch(() => {});
      const source = ctx.createMediaElementSource(el);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 64;
      analyser.smoothingTimeConstant = 0.85;
      source.connect(analyser);
      analyser.connect(ctx.destination);
      sourceRef.current = source;
      analyserRef.current = analyser;
      tappedElRef.current = el;
      setMode('real');
    } catch {
      // createMediaElementSource throws if the element was already tapped
      // (StrictMode double-mount / hot reload). Decorative keeps motion.
      setMode('decorative');
    }
  }, [audioRef, isPlaying, realSpectrum]);

  // Animation loop.
  useEffect(() => {
    if (!isPlaying || mode === 'idle') {
      if (frameRef.current !== null) {
        cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
      }
      return;
    }
    let tick = 0;
    let lastTs = 0;
    let silence = 0;
    const loop = (ts: number) => {
      if (ts - lastTs >= FRAME_INTERVAL_MS) {
        lastTs = ts;
        tick += 1;
        const analyser = analyserRef.current;
        if (mode === 'real' && analyser) {
          const data = new Uint8Array(analyser.frequencyBinCount);
          analyser.getByteFrequencyData(data);
          const sum = data.reduce((a, b) => a + b, 0);
          if (sum === 0) {
            silence += 1;
            if (silence > SILENCE_FRAMES_TO_DECORATIVE) setMode('decorative');
          } else {
            silence = 0;
            setBars(groupBars(data, barCount));
          }
        } else {
          setBars(decorativeBars(barCount, tick));
        }
      }
      frameRef.current = requestAnimationFrame(loop);
    };
    frameRef.current = requestAnimationFrame(loop);
    return () => {
      if (frameRef.current !== null) {
        cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
      }
    };
  }, [isPlaying, mode, barCount]);

  // Tear down audio graph on unmount.
  useEffect(() => {
    return () => {
      if (sourceRef.current) {
        try {
          sourceRef.current.disconnect();
        } catch {
          // ignore
        }
        sourceRef.current = null;
      }
      if (ctxRef.current) {
        const closed = ctxRef.current.close() as Promise<void> | undefined;
        if (closed && typeof closed.catch === 'function') closed.catch(() => {});
        ctxRef.current = null;
        analyserRef.current = null;
        tappedElRef.current = null;
      }
    };
  }, []);

  const displayBars = isPlaying ? bars : Array(barCount).fill(0.15);

  return (
    <div
      aria-hidden
      className={cn('flex h-6 -rotate-1 items-end gap-[2px]', className)}
      data-mode={isPlaying ? mode : 'idle'}
      data-testid="spectrum-analyzer"
    >
      {displayBars.map((value, i) => (
        <div
          key={i}
          className="w-[3px] rounded-xs bg-magenta opacity-85 transition-[height] duration-100"
          style={{ height: `${Math.max(2, value * 24)}px` }}
        />
      ))}
    </div>
  );
}
