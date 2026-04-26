import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { StationStreamRef, StationSummary } from './types';

interface PlayerState {
  currentStation: StationSummary | null;
  isPlaying: boolean;
  isBuffering: boolean;
  volume: number;
  play: (station: StationSummary) => void;
  pause: () => void;
  stop: () => void;
  setBuffering: (buffering: boolean) => void;
  setVolume: (v: number) => void;
  toggle: () => void;
  setStream: (stream: StationStreamRef) => void;
}

export const usePlayerStore = create<PlayerState>()(
  persist(
    (set, get) => ({
      currentStation: null,
      isPlaying: false,
      isBuffering: false,
      volume: 0.8,
      play: (station) =>
        set({
          currentStation: station,
          isPlaying: true,
          isBuffering: true,
        }),
      pause: () => set({ isPlaying: false, isBuffering: false }),
      stop: () => set({ currentStation: null, isPlaying: false, isBuffering: false }),
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
    }),
    {
      name: 'radio-player',
      partialize: (state) => ({ volume: state.volume }),
    },
  ),
);
