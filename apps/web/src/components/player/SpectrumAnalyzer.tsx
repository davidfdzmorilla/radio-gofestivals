'use client';

import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';

interface SpectrumAnalyzerProps {
  audioElement: HTMLAudioElement | null;
  isPlaying: boolean;
  barCount?: number;
  className?: string;
}

type Mode = 'idle' | 'real' | 'decorative';

export function groupBars(dataArray: Uint8Array, targetCount: number): number[] {
  if (targetCount <= 0) return [];
  const groupSize = Math.max(1, Math.floor(dataArray.length / targetCount));
  const groups: number[] = [];
  for (let i = 0; i < targetCount; i++) {
    const start = i * groupSize;
    const end = Math.min(start + groupSize, dataArray.length);
    const slice = dataArray.slice(start, end);
    const sum = slice.reduce((a, b) => a + b, 0);
    const avg = slice.length > 0 ? sum / slice.length : 0;
    groups.push(avg / 255);
  }
  return groups;
}

export function SpectrumAnalyzer({
  audioElement,
  isPlaying,
  barCount = 10,
  className,
}: SpectrumAnalyzerProps) {
  const [bars, setBars] = useState<number[]>(() => Array(barCount).fill(0));
  const [mode, setMode] = useState<Mode>('idle');

  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const silenceFramesRef = useRef(0);

  useEffect(() => {
    if (!audioElement || !isPlaying) return;
    if (audioContextRef.current) {
      // Already wired — resume if the browser suspended it after a tab switch.
      if (audioContextRef.current.state === 'suspended') {
        audioContextRef.current.resume().catch(() => {});
      }
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
      const ctx = new Ctor();
      audioContextRef.current = ctx;
      if (ctx.state === 'suspended') {
        ctx.resume().catch(() => {});
      }
      const source = ctx.createMediaElementSource(audioElement);
      sourceRef.current = source;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 64;
      analyser.smoothingTimeConstant = 0.85;
      source.connect(analyser);
      analyser.connect(ctx.destination);
      analyserRef.current = analyser;
      setMode('real');
    } catch {
      // createMediaElementSource throws InvalidStateError if a source was
      // already created for this element (StrictMode double-mount, hot
      // reload). Fall back to decorative so the user still sees motion.
      setMode('decorative');
    }
  }, [audioElement, isPlaying]);

  useEffect(() => {
    if (!audioElement) return;

    const handleSrcChange = () => {
      const src = sourceRef.current;
      const analyser = analyserRef.current;
      const ctx = audioContextRef.current;
      if (!src || !analyser || !ctx) return;
      try {
        // createMediaElementSource can only be called once per element, so
        // we keep the existing source and refresh the pipeline by
        // disconnecting and reconnecting. This forces the AnalyserNode to
        // re-read from the new audio buffer instead of stale state.
        src.disconnect();
        analyser.disconnect();
        src.connect(analyser);
        analyser.connect(ctx.destination);
        silenceFramesRef.current = 0;
        setMode('real');
      } catch {
        // ignore — keep current mode
      }
    };

    audioElement.addEventListener('loadstart', handleSrcChange);
    return () => {
      audioElement.removeEventListener('loadstart', handleSrcChange);
    };
  }, [audioElement]);

  useEffect(() => {
    if (!isPlaying) {
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      return;
    }

    const tick = () => {
      if (mode === 'real' && analyserRef.current) {
        const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
        analyserRef.current.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) sum += dataArray[i]!;
        if (sum === 0) {
          silenceFramesRef.current += 1;
          if (silenceFramesRef.current > 60) {
            setMode('decorative');
            silenceFramesRef.current = 0;
          }
        } else {
          silenceFramesRef.current = 0;
          setBars(groupBars(dataArray, barCount));
        }
      } else if (mode === 'decorative') {
        setBars((prev) => prev.map(() => Math.random() * 0.7 + 0.2));
      }
      animationFrameRef.current = requestAnimationFrame(tick);
    };

    animationFrameRef.current = requestAnimationFrame(tick);
    return () => {
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    };
  }, [isPlaying, mode, barCount]);

  useEffect(() => {
    return () => {
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (sourceRef.current) {
        try {
          sourceRef.current.disconnect();
        } catch {
          // ignore
        }
        sourceRef.current = null;
      }
      if (audioContextRef.current) {
        try {
          const closed = audioContextRef.current.close() as
            | Promise<void>
            | undefined;
          if (closed && typeof closed.catch === 'function') {
            closed.catch(() => {});
          }
        } catch {
          // ignore
        }
        audioContextRef.current = null;
        analyserRef.current = null;
      }
    };
  }, []);

  return (
    <div
      aria-hidden
      className={cn(
        'flex h-6 -rotate-1 items-end gap-[2px]',
        className,
      )}
      data-mode={mode}
      data-testid="spectrum-analyzer"
    >
      {bars.map((value, i) => (
        <div
          key={i}
          className="w-[3px] rounded-sm bg-magenta opacity-85 transition-[height] duration-75"
          style={{ height: `${Math.max(2, value * 24)}px` }}
        />
      ))}
    </div>
  );
}
