import { z } from 'zod';
import {
  CountryFacetSchema,
  GenreFacetSchema,
  GenreSchema,
  StationDetailSchema,
  StationSummarySchema,
  StationsPageSchema,
  type CountryFacet,
  type Genre,
  type GenreFacet,
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
  schema?: z.ZodType<T, unknown>;
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

const GenresArraySchema = z.array(GenreSchema) as unknown as z.ZodType<Genre[], unknown>;

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
  q?: string;
  page?: number;
  size?: number;
  revalidate?: number;
}

export async function listStations(params: ListStationsParams = {}): Promise<StationsPage> {
  const qs = new URLSearchParams();
  if (params.genre) qs.set('genre', params.genre);
  if (params.country) qs.set('country', params.country);
  if (params.q) qs.set('q', params.q);
  if (params.curated !== undefined) qs.set('curated', String(params.curated));
  if (params.page) qs.set('page', String(params.page));
  if (params.size) qs.set('size', String(params.size));
  const path = `/api/v1/stations${qs.toString() ? `?${qs}` : ''}`;
  return apiFetch(path, {
    schema: StationsPageSchema,
    revalidate: params.revalidate ?? 60,
  });
}

interface ListFeaturedStationsParams {
  size?: number;
  revalidate?: number;
}

export async function listFeaturedStations(
  params: ListFeaturedStationsParams = {},
): Promise<StationsPage> {
  const qs = new URLSearchParams();
  if (params.size) qs.set('size', String(params.size));
  const path = `/api/v1/stations/featured${qs.toString() ? `?${qs}` : ''}`;
  return apiFetch(path, {
    schema: StationsPageSchema,
    revalidate: params.revalidate ?? 300,
  });
}

const CountryFacetsSchema = z.array(CountryFacetSchema);

export async function getCountryFacets(
  params: { genre?: string; revalidate?: number } = {},
): Promise<CountryFacet[]> {
  const qs = new URLSearchParams();
  if (params.genre) qs.set('genre', params.genre);
  const path = `/api/v1/stations/facets/countries${qs.toString() ? `?${qs}` : ''}`;
  return apiFetch(path, {
    schema: CountryFacetsSchema,
    revalidate: params.revalidate ?? 300,
  });
}

const GenreFacetsSchema = z.array(GenreFacetSchema);

export async function getGenreFacets(
  params: { country?: string; revalidate?: number } = {},
): Promise<GenreFacet[]> {
  const qs = new URLSearchParams();
  if (params.country) qs.set('country', params.country);
  const path = `/api/v1/stations/facets/genres${qs.toString() ? `?${qs}` : ''}`;
  return apiFetch(path, {
    schema: GenreFacetsSchema,
    revalidate: params.revalidate ?? 300,
  });
}

export async function listTrendingStations(
  params: { genre?: string; limit?: number; revalidate?: number } = {},
): Promise<StationsPage> {
  const qs = new URLSearchParams();
  if (params.genre) qs.set('genre', params.genre);
  if (params.limit) qs.set('limit', String(params.limit));
  const path = `/api/v1/stations/trending${qs.toString() ? `?${qs}` : ''}`;
  return apiFetch(path, {
    schema: StationsPageSchema,
    revalidate: params.revalidate ?? 300,
  });
}

export async function listNewStations(
  params: { limit?: number; revalidate?: number } = {},
): Promise<StationsPage> {
  const qs = new URLSearchParams();
  if (params.limit) qs.set('limit', String(params.limit));
  const path = `/api/v1/stations/new${qs.toString() ? `?${qs}` : ''}`;
  return apiFetch(path, {
    schema: StationsPageSchema,
    revalidate: params.revalidate ?? 300,
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
