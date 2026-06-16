'use client';

import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';

interface SpectrumAnalyzerProps {
  isPlaying: boolean;
  barCount?: number;
  className?: string;
}

// Decorative-only. We deliberately do NOT tap the <audio> element through
// the Web Audio API: createMediaElementSource silences cross-origin streams
// without CORS (browser taint rule), and most internet-radio streams send
// no CORS headers. A real spectrum would therefore break playback for a
// large slice of the catalog. Bars animate from a seeded pattern so motion
// reads as "audio is playing" without ever touching the stream.
const FRAME_INTERVAL_MS = 90;
const IDLE_HEIGHT = 0.15;

function barHeight(index: number, tick: number): number {
  // Deterministic wave per bar + tick; no Math.random so SSR/tests are
  // stable and it reads as a VU meter rather than pure noise.
  const phase = Math.sin((tick + index * 1.7) / 2.2);
  return 0.25 + ((phase + 1) / 2) * 0.7;
}

export function SpectrumAnalyzer({
  isPlaying,
  barCount = 10,
  className,
}: SpectrumAnalyzerProps) {
  const [tick, setTick] = useState(0);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    if (!isPlaying) return;
    let lastTs = 0;
    const loop = (ts: number) => {
      if (ts - lastTs >= FRAME_INTERVAL_MS) {
        lastTs = ts;
        setTick((t) => t + 1);
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
  }, [isPlaying]);

  // Derived in render — no setState-in-effect for the idle reset.
  const bars = Array.from({ length: barCount }, (_, i) =>
    isPlaying ? barHeight(i, tick) : IDLE_HEIGHT,
  );

  return (
    <div
      aria-hidden
      className={cn('flex h-6 -rotate-1 items-end gap-[2px]', className)}
      data-mode={isPlaying ? 'decorative' : 'idle'}
      data-testid="spectrum-analyzer"
    >
      {bars.map((value, i) => (
        <div
          key={i}
          className="w-[3px] rounded-xs bg-magenta opacity-85 transition-[height] duration-100"
          style={{ height: `${Math.max(2, value * 24)}px` }}
        />
      ))}
    </div>
  );
}
