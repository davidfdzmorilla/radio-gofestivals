export type WSListener = (data: unknown) => void;

const MAX_BACKOFF_MS = 30_000;
const INITIAL_BACKOFF_MS = 1_000;
// El servidor cierra con 1008 a propósito (p. ej. station_not_available):
// reconectar solo repetiría la misma respuesta y gastaría el límite por IP.
const WS_POLICY_VIOLATION = 1008;

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
    this.ws.addEventListener('close', (ev) => {
      if (ev.code === WS_POLICY_VIOLATION) {
        this.closed = true;
        this.onStatus?.(false);
        return;
      }
      this.scheduleReconnect();
    });
    this.ws.addEventListener('error', () => this.scheduleReconnect());
  }

  private scheduleReconnect(): void {
    this.onStatus?.(false);
    // Un fallo dispara 'error' y luego 'close': sin esta guarda programaría
    // dos reconexiones (el doble de conexiones contra el límite por IP).
    if (this.closed || this.reconnectTimer !== null) return;
    const delay = Math.min(
      MAX_BACKOFF_MS,
      INITIAL_BACKOFF_MS * 2 ** this.retries,
    );
    this.retries += 1;
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
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
