import { describe, expect, it, vi, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { SpectrumAnalyzer } from '@/components/player/SpectrumAnalyzer';

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('<SpectrumAnalyzer />', () => {
  it('renders the requested number of bars', () => {
    render(<SpectrumAnalyzer isPlaying={false} barCount={12} />);
    const wrapper = screen.getByTestId('spectrum-analyzer');
    expect(wrapper.children).toHaveLength(12);
  });

  it('is idle when not playing', () => {
    render(<SpectrumAnalyzer isPlaying={false} barCount={6} />);
    expect(screen.getByTestId('spectrum-analyzer').dataset.mode).toBe('idle');
  });

  it('is decorative when playing', () => {
    vi.spyOn(window, 'requestAnimationFrame').mockReturnValue(1);
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {});
    render(<SpectrumAnalyzer isPlaying barCount={8} />);
    expect(screen.getByTestId('spectrum-analyzer').dataset.mode).toBe(
      'decorative',
    );
  });

  it('does not run animation frames while paused', () => {
    const raf = vi.spyOn(window, 'requestAnimationFrame');
    render(<SpectrumAnalyzer isPlaying={false} barCount={4} />);
    expect(raf).not.toHaveBeenCalled();
  });

  it('schedules animation frames while playing', () => {
    const raf = vi.spyOn(window, 'requestAnimationFrame').mockReturnValue(1);
    render(<SpectrumAnalyzer isPlaying barCount={4} />);
    expect(raf).toHaveBeenCalled();
  });

  it('cancels its animation frame on unmount', () => {
    vi.spyOn(window, 'requestAnimationFrame').mockReturnValue(42);
    const cancel = vi
      .spyOn(window, 'cancelAnimationFrame')
      .mockImplementation(() => {});
    const { unmount } = render(<SpectrumAnalyzer isPlaying barCount={4} />);
    act(() => unmount());
    expect(cancel).toHaveBeenCalledWith(42);
  });

  it('never references an audio element (no Web Audio tap)', () => {
    // Regression guard: tapping the <audio> via createMediaElementSource is
    // what silenced cross-origin streams. The component must not need it.
    const ctor = vi.fn();
    (window as unknown as { AudioContext: unknown }).AudioContext = ctor;
    vi.spyOn(window, 'requestAnimationFrame').mockReturnValue(1);
    render(<SpectrumAnalyzer isPlaying barCount={4} />);
    expect(ctor).not.toHaveBeenCalled();
  });
});
