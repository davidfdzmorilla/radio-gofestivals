import { beforeEach, describe, expect, it } from 'vitest';
import { usePlayerStore } from '@/lib/player-store';
import type { StationSummary } from '@/lib/types';

const station: StationSummary = {
  id: '00000000-0000-0000-0000-000000000001',
  slug: 's1',
  name: 'Test',
  country_code: 'ES',
  city: 'Madrid',
  codec: 'mp3',
  bitrate: 128,
  curated: true,
  quality_score: 80,
  genres: ['techno'],
};

describe('usePlayerStore', () => {
  beforeEach(() => {
    usePlayerStore.setState({
      currentStation: null,
      isPlaying: false,
      isBuffering: false,
      volume: 0.8,
    });
  });

  it('play sets currentStation and isPlaying', () => {
    usePlayerStore.getState().play(station);
    const state = usePlayerStore.getState();
    expect(state.currentStation).toEqual(station);
    expect(state.isPlaying).toBe(true);
    expect(state.isBuffering).toBe(true);
  });

  it('pause keeps station but isPlaying=false', () => {
    usePlayerStore.getState().play(station);
    usePlayerStore.getState().pause();
    const state = usePlayerStore.getState();
    expect(state.currentStation).toEqual(station);
    expect(state.isPlaying).toBe(false);
  });

  it('toggle alternates', () => {
    usePlayerStore.getState().play(station);
    usePlayerStore.getState().toggle();
    expect(usePlayerStore.getState().isPlaying).toBe(false);
    usePlayerStore.getState().toggle();
    expect(usePlayerStore.getState().isPlaying).toBe(true);
  });

  it('setVolume clamps 0..1', () => {
    usePlayerStore.getState().setVolume(2);
    expect(usePlayerStore.getState().volume).toBe(1);
    usePlayerStore.getState().setVolume(-0.5);
    expect(usePlayerStore.getState().volume).toBe(0);
    usePlayerStore.getState().setVolume(0.42);
    expect(usePlayerStore.getState().volume).toBe(0.42);
  });

  it('stop clears station', () => {
    usePlayerStore.getState().play(station);
    usePlayerStore.getState().stop();
    expect(usePlayerStore.getState().currentStation).toBeNull();
    expect(usePlayerStore.getState().isPlaying).toBe(false);
  });
});
