import { z } from 'zod';
import {
  GenreSchema,
  StationDetailSchema,
  StationSummarySchema,
  StationsPageSchema,
  type Genre,
  type StationDetail,
  type StationSummary,
  type StationsPage,
} from './types';

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly path: string,
    message?: string,
  ) {
    super(message ?? `API ${status} on ${path}`);
  }
}

interface FetchOpts<T> {
  schema?: z.ZodType<T, z.ZodTypeDef, unknown>;
  revalidate?: number;
  signal?: AbortSignal;
}

export async function apiFetch<T>(path: string, opts: FetchOpts<T> = {}): Promise<T> {
  const url = `${BASE}${path}`;
  const res = await fetch(url, {
    headers: { Accept: 'application/json' },
    signal: opts.signal,
    ...(opts.revalidate !== undefined
      ? { next: { revalidate: opts.revalidate } }
      : {}),
  });
  if (!res.ok) {
    throw new ApiError(res.status, path);
  }
  const data: unknown = await res.json();
  if (opts.schema) {
    return opts.schema.parse(data);
  }
  return data as T;
}

const GenresArraySchema = z.array(GenreSchema) as unknown as z.ZodType<
  Genre[],
  z.ZodTypeDef,
  unknown
>;

export async function getGenresTree(revalidate = 300): Promise<Genre[]> {
  return apiFetch<Genre[]>('/api/v1/genres', {
    schema: GenresArraySchema,
    revalidate,
  });
}

interface ListStationsParams {
  genre?: string;
  country?: string;
  curated?: boolean;
  page?: number;
  size?: number;
  revalidate?: number;
}

export async function listStations(params: ListStationsParams = {}): Promise<StationsPage> {
  const qs = new URLSearchParams();
  if (params.genre) qs.set('genre', params.genre);
  if (params.country) qs.set('country', params.country);
  if (params.curated !== undefined) qs.set('curated', String(params.curated));
  if (params.page) qs.set('page', String(params.page));
  if (params.size) qs.set('size', String(params.size));
  const path = `/api/v1/stations${qs.toString() ? `?${qs}` : ''}`;
  return apiFetch(path, {
    schema: StationsPageSchema,
    revalidate: params.revalidate ?? 60,
  });
}

export async function getStation(
  slug: string,
  revalidate = 60,
): Promise<StationDetail | null> {
  try {
    return await apiFetch<StationDetail>(`/api/v1/stations/${slug}`, {
      schema: StationDetailSchema,
      revalidate,
    });
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export { StationSummarySchema };
export type { StationSummary };
