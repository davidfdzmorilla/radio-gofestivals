import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ReconnectingWebSocket } from '@/lib/ws';

interface MockWSInstance {
  url: string;
  handlers: Record<string, Array<(arg: unknown) => void>>;
  close: ReturnType<typeof vi.fn>;
  readyState: number;
  addEventListener: (name: string, cb: (arg: unknown) => void) => void;
  dispatch: (name: string, payload?: unknown) => void;
}

let instances: MockWSInstance[] = [];

class MockWebSocket {
  static OPEN = 1;
  static CLOSED = 3;
  readyState = 0;
  handlers: Record<string, Array<(arg: unknown) => void>> = {};
  close = vi.fn(() => {
    this.readyState = MockWebSocket.CLOSED;
  });

  constructor(public url: string) {
    const inst: MockWSInstance = {
      url,
      handlers: this.handlers,
      close: this.close,
      readyState: this.readyState,
      addEventListener: this.addEventListener.bind(this),
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

describe('ReconnectingWebSocket', () => {
  beforeEach(() => {
    instances = [];
    vi.useFakeTimers();
    (globalThis as unknown as { WebSocket: typeof MockWebSocket }).WebSocket =
      MockWebSocket;
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('connects on construction', () => {
    const ws = new ReconnectingWebSocket('ws://x', () => {});
    ws.connect();
    expect(instances).toHaveLength(1);
    expect(instances[0]!.url).toBe('ws://x');
    ws.close();
  });

  it('calls onMessage with parsed JSON', () => {
    const onMsg = vi.fn();
    const ws = new ReconnectingWebSocket('ws://x', onMsg);
    ws.connect();
    instances[0]!.dispatch('message', { data: '{"title":"A","at":"t"}' });
    expect(onMsg).toHaveBeenCalledWith({ title: 'A', at: 't' });
    ws.close();
  });

  it('retries with exponential backoff (1s, 2s, 4s, 8s, cap 30s)', () => {
    const ws = new ReconnectingWebSocket('ws://x', () => {});
    ws.connect();

    // Primera close → próxima conexión en ~1000ms
    instances[0]!.dispatch('close');
    vi.advanceTimersByTime(1000);
    expect(instances).toHaveLength(2);

    instances[1]!.dispatch('close');
    vi.advanceTimersByTime(2000);
    expect(instances).toHaveLength(3);

    instances[2]!.dispatch('close');
    vi.advanceTimersByTime(4000);
    expect(instances).toHaveLength(4);

    instances[3]!.dispatch('close');
    vi.advanceTimersByTime(8000);
    expect(instances).toHaveLength(5);

    ws.close();
  });

  it('resets retry counter on open', () => {
    const ws = new ReconnectingWebSocket('ws://x', () => {});
    ws.connect();

    instances[0]!.dispatch('close');
    vi.advanceTimersByTime(1000);
    instances[1]!.dispatch('close');
    vi.advanceTimersByTime(2000);

    // Tercera instancia, simula conexión OK
    instances[2]!.dispatch('open');
    instances[2]!.dispatch('close');
    vi.advanceTimersByTime(1000);
    expect(instances).toHaveLength(4); // vuelve a backoff inicial

    ws.close();
  });

  it('close() is idempotent and stops reconnects', () => {
    const ws = new ReconnectingWebSocket('ws://x', () => {});
    ws.connect();
    ws.close();
    const before = instances.length;
    vi.advanceTimersByTime(60_000);
    expect(instances.length).toBe(before);
  });
});
