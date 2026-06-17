import { describe, expect, it, vi, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { SpectrumAnalyzer, groupBars } from '@/components/player/SpectrumAnalyzer';

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

function fakeAudioContext() {
  const fakeAnalyser = {
    fftSize: 64,
    smoothingTimeConstant: 0.85,
    frequencyBinCount: 32,
    getByteFrequencyData: (arr: Uint8Array) => {
      for (let i = 0; i < arr.length; i++) arr[i] = 0; // silence by default
    },
    connect: vi.fn(),
    disconnect: vi.fn(),
  } as unknown as AnalyserNode;
  const fakeSource = { connect: vi.fn(), disconnect: vi.fn() };
  const fakeCtx = {
    state: 'running',
    resume: vi.fn().mockResolvedValue(undefined),
    close: vi.fn().mockResolvedValue(undefined),
    destination: {} as AudioDestinationNode,
    createMediaElementSource: vi.fn().mockReturnValue(fakeSource),
    createAnalyser: vi.fn().mockReturnValue(fakeAnalyser),
  };
  const ctor = vi.fn().mockImplementation(function (this: unknown) {
    return fakeCtx;
  });
  (window as unknown as { AudioContext: unknown }).AudioContext = ctor;
  return { ctor, fakeCtx, fakeAnalyser, fakeSource };
}

describe('groupBars', () => {
  it('produces N groups normalized to [0,1]', () => {
    const data = new Uint8Array(32).fill(255);
    const groups = groupBars(data, 8);
    expect(groups).toHaveLength(8);
    for (const g of groups) expect(g).toBeCloseTo(1, 5);
  });

  it('handles targetCount=0', () => {
    expect(groupBars(new Uint8Array(8), 0)).toEqual([]);
  });
});

describe('<SpectrumAnalyzer />', () => {
  it('renders the requested number of bars', () => {
    render(
      <SpectrumAnalyzer
        audioRef={{ current: null }}
        isPlaying={false}
        realSpectrum={false}
        barCount={12}
      />,
    );
    expect(screen.getByTestId('spectrum-analyzer').children).toHaveLength(12);
  });

  it('is idle when not playing', () => {
    render(
      <SpectrumAnalyzer
        audioRef={{ current: null }}
        isPlaying={false}
        realSpectrum
        barCount={6}
      />,
    );
    expect(screen.getByTestId('spectrum-analyzer').dataset.mode).toBe('idle');
  });

  it('does not run animation frames while paused', () => {
    const raf = vi.spyOn(window, 'requestAnimationFrame');
    render(
      <SpectrumAnalyzer
        audioRef={{ current: null }}
        isPlaying={false}
        realSpectrum
        barCount={4}
      />,
    );
    expect(raf).not.toHaveBeenCalled();
  });

  it('NEVER taps Web Audio when realSpectrum is false (the CORS fix)', () => {
    const { ctor } = fakeAudioContext();
    vi.spyOn(window, 'requestAnimationFrame').mockReturnValue(1);
    const audio = document.createElement('audio');
    render(
      <SpectrumAnalyzer
        audioRef={{ current: audio }}
        isPlaying
        realSpectrum={false}
        barCount={8}
      />,
    );
    expect(ctor).not.toHaveBeenCalled();
    expect(screen.getByTestId('spectrum-analyzer').dataset.mode).toBe(
      'decorative',
    );
  });

  it('taps Web Audio and goes real when realSpectrum is true', () => {
    const { ctor, fakeCtx } = fakeAudioContext();
    vi.spyOn(window, 'requestAnimationFrame').mockReturnValue(1);
    const audio = document.createElement('audio');
    render(
      <SpectrumAnalyzer
        audioRef={{ current: audio }}
        isPlaying
        realSpectrum
        barCount={8}
      />,
    );
    expect(ctor).toHaveBeenCalledTimes(1);
    expect(fakeCtx.createMediaElementSource).toHaveBeenCalledWith(audio);
    expect(screen.getByTestId('spectrum-analyzer').dataset.mode).toBe('real');
  });

  it('falls back to decorative after sustained silence on a real analyser', () => {
    let frameCb: FrameRequestCallback | null = null;
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
      frameCb = cb;
      return 1;
    });
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {});
    fakeAudioContext();

    const audio = document.createElement('audio');
    render(
      <SpectrumAnalyzer
        audioRef={{ current: audio }}
        isPlaying
        realSpectrum
        barCount={8}
      />,
    );
    const wrapper = screen.getByTestId('spectrum-analyzer');
    expect(wrapper.dataset.mode).toBe('real');

    act(() => {
      // 90ms spacing clears the throttle each frame; >60 silent frames flip it.
      for (let i = 0; i < 65; i++) {
        if (!frameCb) break;
        const cb = frameCb;
        frameCb = null;
        cb(i * 100);
      }
    });
    expect(wrapper.dataset.mode).toBe('decorative');
  });

  it('re-taps the new element when it changes (CORS boundary remount)', () => {
    const { fakeCtx } = fakeAudioContext();
    vi.spyOn(window, 'requestAnimationFrame').mockReturnValue(1);
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {});

    const audioA = document.createElement('audio');
    const { rerender } = render(
      <SpectrumAnalyzer
        audioRef={{ current: audioA }}
        isPlaying
        realSpectrum
        barCount={8}
      />,
    );
    expect(fakeCtx.createMediaElementSource).toHaveBeenCalledWith(audioA);

    // Cross to a plain (no-CORS) station: element remounts, realSpectrum off.
    rerender(
      <SpectrumAnalyzer
        audioRef={{ current: audioA }}
        isPlaying
        realSpectrum={false}
        barCount={8}
      />,
    );
    // Back to a CORS station with a FRESH element.
    const audioB = document.createElement('audio');
    rerender(
      <SpectrumAnalyzer
        audioRef={{ current: audioB }}
        isPlaying
        realSpectrum
        barCount={8}
      />,
    );
    expect(fakeCtx.createMediaElementSource).toHaveBeenCalledWith(audioB);
  });
});
