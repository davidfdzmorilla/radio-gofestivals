import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { StationStreamRef, StationSummary } from './types';

interface PlayerState {
  currentStation: StationSummary | null;
  // Full list of variants for fallback. Cards on the home don't pass it
  // (they only have primary_stream); when they call play() we synthesise
  // a single-element list from primary_stream so the API stays uniform.
  streams: StationStreamRef[];
  // IDs of streams that already failed for the current station. Persisted
  // as array because Set isn't JSON-serialisable (and we partialise out of
  // persist, but the array form keeps the door open for future opt-in).
  failedStreamIds: string[];
  error: string | null;
  isPlaying: boolean;
  isBuffering: boolean;
  volume: number;
  play: (station: StationSummary, streams?: StationStreamRef[]) => void;
  pause: () => void;
  stop: () => void;
  setBuffering: (buffering: boolean) => void;
  setVolume: (v: number) => void;
  toggle: () => void;
  setStream: (stream: StationStreamRef) => void;
  setError: (msg: string | null) => void;
  tryNextFallback: () => boolean;
  resetFallbacks: () => void;
  retry: () => void;
}

function _streamsFor(
  station: StationSummary,
  streams?: StationStreamRef[],
): StationStreamRef[] {
  if (streams && streams.length > 0) return streams;
  return station.primary_stream ? [station.primary_stream] : [];
}

export const usePlayerStore = create<PlayerState>()(
  persist(
    (set, get) => ({
      currentStation: null,
      streams: [],
      failedStreamIds: [],
      error: null,
      isPlaying: false,
      isBuffering: false,
      volume: 0.8,
      play: (station, streams) =>
        set({
          currentStation: station,
          streams: _streamsFor(station, streams),
          failedStreamIds: [],
          error: null,
          isPlaying: true,
          isBuffering: true,
        }),
      pause: () => set({ isPlaying: false, isBuffering: false }),
      stop: () =>
        set({
          currentStation: null,
          streams: [],
          failedStreamIds: [],
          error: null,
          isPlaying: false,
          isBuffering: false,
        }),
      setBuffering: (buffering) => set({ isBuffering: buffering }),
      setVolume: (v) => set({ volume: Math.max(0, Math.min(1, v)) }),
      toggle: () => {
        const { currentStation, isPlaying } = get();
        if (!currentStation) return;
        set({ isPlaying: !isPlaying, isBuffering: !isPlaying });
      },
      setStream: (stream) => {
        const cur = get().currentStation;
        if (!cur) return;
        set({ currentStation: { ...cur, primary_stream: stream } });
      },
      setError: (msg) => set({ error: msg }),
      tryNextFallback: () => {
        const station = get().currentStation;
        const all = get().streams;
        if (!station || all.length === 0) return false;

        const failed = new Set(get().failedStreamIds);
        const current = station.primary_stream;
        if (current) failed.add(current.id);

        const next = all
          .filter((s) => s.status === 'active')
          .find((s) => !failed.has(s.id));

        if (!next) {
          set({
            failedStreamIds: Array.from(failed),
            error: 'streamUnavailable',
            isPlaying: false,
            isBuffering: false,
          });
          return false;
        }

        set({ failedStreamIds: Array.from(failed), error: null });
        // setStream rewrites currentStation.primary_stream → GlobalPlayer's
        // effect picks up the URL change and runs pause-load-play.
        get().setStream(next);
        return true;
      },
      resetFallbacks: () => set({ failedStreamIds: [], error: null }),
      retry: () => {
        const all = get().streams;
        if (all.length === 0) return;
        const primary = all.find((s) => s.is_primary) ?? all[0]!;
        set({
          failedStreamIds: [],
          error: null,
          isPlaying: true,
          isBuffering: true,
        });
        get().setStream(primary);
      },
    }),
    {
      name: 'radio-player',
      partialize: (state) => ({ volume: state.volume }),
    },
  ),
);
