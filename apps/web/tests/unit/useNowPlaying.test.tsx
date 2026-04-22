import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useNowPlaying } from '@/hooks/useNowPlaying';

interface MockWSInstance {
  url: string;
  handlers: Record<string, Array<(arg: unknown) => void>>;
  close: ReturnType<typeof vi.fn>;
  dispatch: (name: string, payload?: unknown) => void;
}

let instances: MockWSInstance[] = [];

class MockWebSocket {
  static OPEN = 1;
  static CLOSED = 3;
  readyState = 0;
  handlers: Record<string, Array<(arg: unknown) => void>> = {};
  close = vi.fn();

  constructor(public url: string) {
    const inst: MockWSInstance = {
      url,
      handlers: this.handlers,
      close: this.close,
      dispatch: this.dispatch.bind(this),
    };
    instances.push(inst);
  }

  addEventListener(name: string, cb: (arg: unknown) => void): void {
    (this.handlers[name] ??= []).push(cb);
  }

  dispatch(name: string, payload?: unknown): void {
    (this.handlers[name] ?? []).forEach((cb) => cb(payload ?? {}));
  }
}

describe('useNowPlaying', () => {
  beforeEach(() => {
    instances = [];
    (globalThis as unknown as { WebSocket: typeof MockWebSocket }).WebSocket =
      MockWebSocket;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('connects to the WS URL with slug', () => {
    renderHook(() => useNowPlaying('test-slug'));
    expect(instances).toHaveLength(1);
    expect(instances[0]!.url).toContain('/api/v1/ws/nowplaying/test-slug');
  });

  it('updates state on valid message', () => {
    const { result } = renderHook(() => useNowPlaying('slug'));
    act(() => {
      instances[0]!.dispatch('message', {
        data: JSON.stringify({ title: 'Hi', artist: 'Me', at: 'now' }),
      });
    });
    expect(result.current.state).toEqual({ title: 'Hi', artist: 'Me', at: 'now' });
  });

  it('ignores heartbeat messages', () => {
    const { result } = renderHook(() => useNowPlaying('slug'));
    act(() => {
      instances[0]!.dispatch('message', {
        data: JSON.stringify({ heartbeat: true }),
      });
    });
    expect(result.current.state).toBeNull();
  });

  it('closes WS on unmount', () => {
    const { unmount } = renderHook(() => useNowPlaying('slug'));
    expect(instances[0]!.close).not.toHaveBeenCalled();
    unmount();
    expect(instances[0]!.close).toHaveBeenCalled();
  });

  it('does nothing when slug is null', () => {
    renderHook(() => useNowPlaying(null));
    expect(instances).toHaveLength(0);
  });
});
