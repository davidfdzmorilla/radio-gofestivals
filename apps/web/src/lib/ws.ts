export type WSListener = (data: unknown) => void;

const MAX_BACKOFF_MS = 30_000;
const INITIAL_BACKOFF_MS = 1_000;

export class ReconnectingWebSocket {
  private ws: WebSocket | null = null;
  private retries = 0;
  private closed = false;
  private reconnectTimer: number | null = null;

  constructor(
    private readonly url: string,
    private readonly onMessage: WSListener,
    private readonly onStatus?: (connected: boolean) => void,
  ) {}

  connect(): void {
    if (this.closed) return;
    this.ws = new WebSocket(this.url);
    this.ws.addEventListener('open', () => {
      this.retries = 0;
      this.onStatus?.(true);
    });
    this.ws.addEventListener('message', (ev) => {
      try {
        const parsed: unknown = JSON.parse(String(ev.data));
        this.onMessage(parsed);
      } catch {
        /* ignore malformed payload */
      }
    });
    this.ws.addEventListener('close', () => this.scheduleReconnect());
    this.ws.addEventListener('error', () => this.scheduleReconnect());
  }

  private scheduleReconnect(): void {
    this.onStatus?.(false);
    if (this.closed) return;
    const delay = Math.min(
      MAX_BACKOFF_MS,
      INITIAL_BACKOFF_MS * 2 ** this.retries,
    );
    this.retries += 1;
    this.reconnectTimer = window.setTimeout(() => this.connect(), delay);
  }

  close(): void {
    this.closed = true;
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws && this.ws.readyState <= WebSocket.OPEN) {
      this.ws.close();
    }
    this.ws = null;
  }
}
