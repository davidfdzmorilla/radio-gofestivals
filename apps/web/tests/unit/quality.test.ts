import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  findPreferredStream,
  inferQualityTier,
  persistQualityPreference,
  readQualityPreference,
} from '@/lib/quality';
import type { StationStreamRef } from '@/lib/types';

const KEY = 'radio.gofestivals.preferredQuality';

const mk = (
  id: string,
  bitrate: number | null,
  is_primary = false,
): StationStreamRef => ({
  id,
  url: `https://example/${id}`,
  codec: 'mp3',
  bitrate,
  format: 'mp3',
  is_primary,
});

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  window.localStorage.clear();
});

describe('inferQualityTier', () => {
  it('classifies by bitrate', () => {
    expect(inferQualityTier(mk('a', 320))).toBe('high');
    expect(inferQualityTier(mk('a', 192))).toBe('high');
    expect(inferQualityTier(mk('a', 128))).toBe('medium');
    expect(inferQualityTier(mk('a', 64))).toBe('low');
    expect(inferQualityTier(mk('a', null))).toBe('low');
  });
});

describe('readQualityPreference', () => {
  it('returns null when nothing stored', () => {
    expect(readQualityPreference()).toBeNull();
  });

  it('returns the stored tier when valid', () => {
    window.localStorage.setItem(KEY, 'high');
    expect(readQualityPreference()).toBe('high');
  });

  it('rejects garbage values', () => {
    window.localStorage.setItem(KEY, 'turbo');
    expect(readQualityPreference()).toBeNull();
  });
});

describe('persistQualityPreference', () => {
  it('writes the inferred tier', () => {
    persistQualityPreference(mk('a', 320));
    expect(window.localStorage.getItem(KEY)).toBe('high');
    persistQualityPreference(mk('b', 64));
    expect(window.localStorage.getItem(KEY)).toBe('low');
  });
});

describe('findPreferredStream', () => {
  const streams = [
    mk('hi', 320, true),
    mk('mid', 128),
    mk('lo', 64),
  ];

  it('returns primary when no preference stored', () => {
    expect(findPreferredStream(streams).id).toBe('hi');
  });

  it('returns the only stream when length is 1', () => {
    expect(findPreferredStream([mk('only', 96)]).id).toBe('only');
  });

  it('high tier picks the lowest stream above 192 floor', () => {
    window.localStorage.setItem(KEY, 'high');
    // hi is the only one >= 192
    expect(findPreferredStream(streams).id).toBe('hi');
  });

  it('medium tier prefers mid (>=96, lowest above floor)', () => {
    window.localStorage.setItem(KEY, 'medium');
    // both mid (128) and hi (320) are >= 96; lowest above floor wins → mid
    expect(findPreferredStream(streams).id).toBe('mid');
  });

  it('low tier picks the smallest available', () => {
    window.localStorage.setItem(KEY, 'low');
    // floor 0 → all match; lowest bitrate wins → lo
    expect(findPreferredStream(streams).id).toBe('lo');
  });

  it('falls back to primary when no candidate clears the floor', () => {
    window.localStorage.setItem(KEY, 'high');
    const onlyLow = [mk('a', 64, true), mk('b', 32)];
    expect(findPreferredStream(onlyLow).id).toBe('a');
  });
});
