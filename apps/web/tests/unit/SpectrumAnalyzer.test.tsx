import { describe, expect, it, vi, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { SpectrumAnalyzer, groupBars } from '@/components/player/SpectrumAnalyzer';

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('groupBars', () => {
  it('produces N groups normalized to [0,1]', () => {
    const data = new Uint8Array(32);
    for (let i = 0; i < 32; i++) data[i] = 255;
    const groups = groupBars(data, 8);
    expect(groups).toHaveLength(8);
    for (const g of groups) expect(g).toBeCloseTo(1, 5);
  });

  it('averages within each group', () => {
    const data = new Uint8Array([0, 0, 255, 255]);
    const groups = groupBars(data, 2);
    expect(groups).toHaveLength(2);
    expect(groups[0]).toBeCloseTo(0, 5);
    expect(groups[1]).toBeCloseTo(1, 5);
  });

  it('handles targetCount=0 gracefully', () => {
    expect(groupBars(new Uint8Array(8), 0)).toEqual([]);
  });
});

describe('<SpectrumAnalyzer />', () => {
  it('renders the requested number of bars', () => {
    render(<SpectrumAnalyzer audioElement={null} isPlaying={false} barCount={12} />);
    const wrapper = screen.getByTestId('spectrum-analyzer');
    expect(wrapper.children).toHaveLength(12);
  });

  it('starts in idle mode when audioElement is null', () => {
    render(<SpectrumAnalyzer audioElement={null} isPlaying barCount={6} />);
    const wrapper = screen.getByTestId('spectrum-analyzer');
    expect(wrapper.dataset.mode).toBe('idle');
  });

  it('does not run animation frames while paused', () => {
    const raf = vi.spyOn(window, 'requestAnimationFrame');
    render(<SpectrumAnalyzer audioElement={null} isPlaying={false} barCount={4} />);
    expect(raf).not.toHaveBeenCalled();
  });

  it('switches to decorative mode after sustained silence on a real analyser', () => {
    let frameCb: FrameRequestCallback | null = null;
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
      frameCb = cb;
      return 1;
    });
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {});

    const fakeAnalyser = {
      fftSize: 64,
      smoothingTimeConstant: 0.85,
      frequencyBinCount: 32,
      getByteFrequencyData: (arr: Uint8Array) => {
        for (let i = 0; i < arr.length; i++) arr[i] = 0;
      },
      connect: vi.fn(),
    } as unknown as AnalyserNode;
    const fakeSource = { connect: vi.fn() };
    const fakeCtx = {
      state: 'running',
      resume: vi.fn().mockResolvedValue(undefined),
      close: vi.fn().mockResolvedValue(undefined),
      destination: {} as AudioDestinationNode,
      createMediaElementSource: vi.fn().mockReturnValue(fakeSource),
      createAnalyser: vi.fn().mockReturnValue(fakeAnalyser),
    };
    (window as unknown as { AudioContext: unknown }).AudioContext = vi
      .fn()
      .mockImplementation(() => fakeCtx);

    const audio = document.createElement('audio');
    render(<SpectrumAnalyzer audioElement={audio} isPlaying barCount={8} />);

    const wrapper = screen.getByTestId('spectrum-analyzer');
    expect(wrapper.dataset.mode).toBe('real');

    act(() => {
      for (let i = 0; i < 65; i++) {
        if (!frameCb) break;
        const cb = frameCb;
        frameCb = null;
        cb(performance.now());
      }
    });

    expect(wrapper.dataset.mode).toBe('decorative');
  });
});
