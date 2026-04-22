'use client';

import { useEffect, useState } from 'react';
import { ReconnectingWebSocket } from '@/lib/ws';
import type { NowPlayingState } from '@/lib/types';

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000';

function isState(raw: unknown): raw is NowPlayingState {
  if (typeof raw !== 'object' || raw === null) return false;
  const obj = raw as Record<string, unknown>;
  if ('heartbeat' in obj) return false;
  return 'at' in obj && typeof obj.at === 'string';
}

export function useNowPlaying(slug: string | null): {
  state: NowPlayingState | null;
  connected: boolean;
} {
  const [state, setState] = useState<NowPlayingState | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!slug) return;
    setState(null);
    const url = `${WS_BASE}/api/v1/ws/nowplaying/${slug}`;
    const ws = new ReconnectingWebSocket(
      url,
      (raw) => {
        if (isState(raw)) setState(raw);
      },
      setConnected,
    );
    ws.connect();
    return () => {
      ws.close();
      setConnected(false);
    };
  }, [slug]);

  return { state, connected };
}
