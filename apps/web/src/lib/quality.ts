import type { StationStreamRef } from './types';

export type QualityTier = 'high' | 'medium' | 'low';

const STORAGE_KEY = 'radio.gofestivals.preferredQuality';

const TIER_FLOOR: Record<QualityTier, number> = {
  high: 192,
  medium: 96,
  low: 0,
};

export function inferQualityTier(stream: StationStreamRef): QualityTier {
  const bitrate = stream.bitrate ?? 0;
  if (bitrate >= TIER_FLOOR.high) return 'high';
  if (bitrate >= TIER_FLOOR.medium) return 'medium';
  return 'low';
}

export function readQualityPreference(): QualityTier | null {
  if (typeof window === 'undefined') return null;
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    if (v === 'high' || v === 'medium' || v === 'low') return v;
    return null;
  } catch {
    return null;
  }
}

export function persistQualityPreference(stream: StationStreamRef): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(STORAGE_KEY, inferQualityTier(stream));
  } catch {
    // private mode etc. — silently swallow
  }
}

export function findPreferredStream(
  streams: StationStreamRef[],
): StationStreamRef {
  if (streams.length === 0) {
    throw new Error('findPreferredStream: empty streams array');
  }
  const primary = streams.find((s) => s.is_primary) ?? streams[0]!;
  if (streams.length === 1) return streams[0]!;

  const tier = readQualityPreference();
  if (!tier) return primary;

  const floor = TIER_FLOOR[tier];
  // Highest bitrate that does not exceed the user's tier ceiling. We honour
  // the floor of the chosen tier; among matches we want the one closest to it.
  const matches = streams
    .filter((s) => (s.bitrate ?? 0) >= floor)
    .sort((a, b) => (a.bitrate ?? 0) - (b.bitrate ?? 0));
  return matches[0] ?? primary;
}

/** Etiqueta visible de una variante de stream, p. ej. "320 aac". */
export function streamLabel(stream: StationStreamRef): string {
  const codec = stream.codec ?? stream.format ?? '?';
  const bitrate = stream.bitrate != null ? String(stream.bitrate) : '—';
  return `${bitrate} ${codec}`;
}

/**
 * Una variante por etiqueta. Dos streams con el mismo códec y bitrate son
 * espejos, no calidades distintas: mostrarlos como dos chips idénticos
 * ("320 AAC" · "320 AAC") confunde. Si el activo está en un grupo, ese es el
 * representante (así sigue marcado); si no, el primero.
 */
export function dedupeStreamsByLabel(
  streams: StationStreamRef[],
  activeStreamId: string | null,
): StationStreamRef[] {
  const byLabel = new Map<string, StationStreamRef>();
  for (const stream of streams) {
    const label = streamLabel(stream);
    const current = byLabel.get(label);
    if (current === undefined || stream.id === activeStreamId) {
      byLabel.set(label, stream);
    }
  }
  // Mantiene el orden de primera aparición de cada etiqueta.
  const order = [...new Set(streams.map(streamLabel))];
  return order.map((label) => byLabel.get(label)!);
}
