import { z } from 'zod';
import { apiFetch } from '@/lib/api';
import {
  StationSummarySchema,
  StationsPageSchema,
  type StationSummary,
  type StationsPage,
} from './types';

export type RecSurface = 'home_for_you' | 'station_similar';

export interface RecEvent {
  station_id: string;
  event_type: 'impression' | 'click';
  slot?: number;
}

/**
 * Recomendaciones personalizadas. Sin clientId (no consent / primera
 * visita) el backend responde el cold start del locale — nunca vacío
 * mientras haya catálogo.
 */
export async function getRecommendedStations(params: {
  clientId?: string | null;
  locale?: string;
  size?: number;
}): Promise<StationsPage> {
  const search = new URLSearchParams();
  if (params.clientId) search.set('client_id', params.clientId);
  if (params.locale) search.set('locale', params.locale);
  search.set('size', String(params.size ?? 12));
  return apiFetch(`/api/v1/stations/recommended?${search.toString()}`, {
    schema: StationsPageSchema,
  });
}

export async function getSimilarStations(
  slug: string,
  opts: { size?: number; revalidate?: number } = {},
): Promise<StationSummary[]> {
  const size = opts.size ?? 6;
  return apiFetch(`/api/v1/stations/${slug}/similar?size=${size}`, {
    schema: z.array(StationSummarySchema),
    revalidate: opts.revalidate,
  });
}

/**
 * Impresiones/clicks del módulo de recomendaciones. Fire-and-forget con
 * keepalive: la evaluación no puede romper la navegación. Sin identidad
 * (no consent) no se envía nada — mismo criterio GDPR que los plays.
 */
export function sendRecEvents(payload: {
  surface: RecSurface;
  clientId: string | null;
  events: RecEvent[];
}): void {
  if (!payload.clientId || payload.events.length === 0) return;
  const base = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
  void fetch(`${base}/api/v1/recs/events`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    keepalive: true,
    body: JSON.stringify({
      surface: payload.surface,
      client_id: payload.clientId,
      events: payload.events,
    }),
  }).catch(() => {
    // tracking best-effort
  });
}
