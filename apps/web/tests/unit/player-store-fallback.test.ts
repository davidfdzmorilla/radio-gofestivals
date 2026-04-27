import { beforeEach, describe, expect, it } from 'vitest';
import { usePlayerStore } from '@/lib/player-store';
import type { StationStreamRef, StationSummary } from '@/lib/types';

const mkStream = (
  id: string,
  bitrate: number,
  is_primary = false,
  status: 'active' | 'broken' | 'inactive' = 'active',
): StationStreamRef => ({
  id,
  url: `https://stream/${id}`,
  codec: 'mp3',
  bitrate,
  format: 'mp3',
  is_primary,
  status,
});

const baseSummary = (
  primary: StationStreamRef,
): StationSummary => ({
  id: 'station-1',
  slug: 'sub-fm',
  name: 'Sub FM',
  country_code: 'GB',
  city: null,
  curated: true,
  quality_score: 75,
  genres: [],
  primary_stream: primary,
});

beforeEach(() => {
  usePlayerStore.setState({
    currentStation: null,
    streams: [],
    failedStreamIds: [],
    error: null,
    isPlaying: false,
    isBuffering: false,
  });
});

describe('tryNextFallback', () => {
  it('advances to the next active stream when current fails', () => {
    const hi = mkStream('hi', 320, true);
    const mid = mkStream('mid', 128);
    const lo = mkStream('lo', 64);
    usePlayerStore.getState().play(baseSummary(hi), [hi, mid, lo]);

    const ok = usePlayerStore.getState().tryNextFallback();
    expect(ok).toBe(true);
    expect(usePlayerStore.getState().currentStation?.primary_stream?.id).toBe(
      'mid',
    );
    expect(usePlayerStore.getState().failedStreamIds).toContain('hi');
    expect(usePlayerStore.getState().error).toBeNull();
  });

  it('walks through every stream until exhaustion', () => {
    const a = mkStream('a', 320, true);
    const b = mkStream('b', 192);
    const c = mkStream('c', 96);
    usePlayerStore.getState().play(baseSummary(a), [a, b, c]);

    expect(usePlayerStore.getState().tryNextFallback()).toBe(true);
    expect(usePlayerStore.getState().currentStation?.primary_stream?.id).toBe('b');

    expect(usePlayerStore.getState().tryNextFallback()).toBe(true);
    expect(usePlayerStore.getState().currentStation?.primary_stream?.id).toBe('c');

    expect(usePlayerStore.getState().tryNextFallback()).toBe(false);
    expect(usePlayerStore.getState().error).toBe('streamUnavailable');
    expect(usePlayerStore.getState().isPlaying).toBe(false);
  });

  it('skips streams marked broken by backend', () => {
    const a = mkStream('a', 320, true);
    const broken = mkStream('b', 256, false, 'broken');
    const c = mkStream('c', 64);
    usePlayerStore.getState().play(baseSummary(a), [a, broken, c]);

    const ok = usePlayerStore.getState().tryNextFallback();
    expect(ok).toBe(true);
    // jumps directly to 'c' because 'b' is broken
    expect(usePlayerStore.getState().currentStation?.primary_stream?.id).toBe('c');
  });

  it('returns false when there is no current station', () => {
    expect(usePlayerStore.getState().tryNextFallback()).toBe(false);
  });
});

describe('play() and resetFallbacks', () => {
  it('clears failed list and error when starting a new station', () => {
    const a = mkStream('a', 320, true);
    const b = mkStream('b', 128);
    usePlayerStore.getState().play(baseSummary(a), [a, b]);
    usePlayerStore.getState().tryNextFallback();
    usePlayerStore.getState().tryNextFallback();
    expect(usePlayerStore.getState().error).toBe('streamUnavailable');

    const otherPrimary = mkStream('p2', 192, true);
    const other: StationSummary = {
      ...baseSummary(otherPrimary),
      id: 'station-2',
      slug: 'other',
    };
    usePlayerStore.getState().play(other, [otherPrimary]);

    expect(usePlayerStore.getState().failedStreamIds).toEqual([]);
    expect(usePlayerStore.getState().error).toBeNull();
    expect(usePlayerStore.getState().currentStation?.id).toBe('station-2');
  });

  it('resetFallbacks clears the failed set', () => {
    const a = mkStream('a', 320, true);
    const b = mkStream('b', 128);
    usePlayerStore.getState().play(baseSummary(a), [a, b]);
    usePlayerStore.getState().tryNextFallback();
    expect(usePlayerStore.getState().failedStreamIds.length).toBeGreaterThan(0);
    usePlayerStore.getState().resetFallbacks();
    expect(usePlayerStore.getState().failedStreamIds).toEqual([]);
    expect(usePlayerStore.getState().error).toBeNull();
  });
});

describe('retry', () => {
  it('clears state and switches back to the primary', () => {
    const primary = mkStream('hi', 320, true);
    const secondary = mkStream('mid', 128);
    usePlayerStore.getState().play(baseSummary(primary), [primary, secondary]);
    usePlayerStore.getState().tryNextFallback();
    usePlayerStore.getState().tryNextFallback();
    expect(usePlayerStore.getState().error).toBe('streamUnavailable');

    usePlayerStore.getState().retry();

    expect(usePlayerStore.getState().error).toBeNull();
    expect(usePlayerStore.getState().failedStreamIds).toEqual([]);
    expect(usePlayerStore.getState().currentStation?.primary_stream?.id).toBe('hi');
    expect(usePlayerStore.getState().isPlaying).toBe(true);
  });
});

describe('play() with single primary_stream (cards path)', () => {
  it('synthesises a one-element streams list when none provided', () => {
    const primary = mkStream('only', 128, true);
    usePlayerStore.getState().play(baseSummary(primary));
    expect(usePlayerStore.getState().streams).toHaveLength(1);
    expect(usePlayerStore.getState().streams[0]!.id).toBe('only');
    // No fallback possible; tryNext returns false immediately.
    expect(usePlayerStore.getState().tryNextFallback()).toBe(false);
  });
});
