import { adminFetch } from './api';

export type StationStatus =
  | 'pending'
  | 'active'
  | 'broken'
  | 'rejected'
  | 'duplicate'
  | 'inactive';

export type StationStatusFilter = StationStatus;

export interface PrimaryStreamRef {
  id: string;
  url: string;
  codec: string | null;
  bitrate: number | null;
}

export interface StationListItem {
  id: string;
  slug: string;
  name: string;
  status: StationStatus;
  curated: boolean;
  country_code: string | null;
  quality_score: number;
  primary_stream: PrimaryStreamRef | null;
  stream_count: number;
  genre_count: number;
  created_at: string;
  last_sync_at: string | null;
}

export interface StationListPage {
  items: StationListItem[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface StationListFilters {
  status?: StationStatusFilter;
  curated?: boolean;
  search?: string;
  page?: number;
  size?: number;
}

export async function listStations(
  filters: StationListFilters = {},
): Promise<StationListPage> {
  const params = new URLSearchParams();
  if (filters.status) params.set('status', filters.status);
  if (filters.curated !== undefined) {
    params.set('curated', filters.curated ? 'true' : 'false');
  }
  if (filters.search) params.set('search', filters.search);
  if (filters.page !== undefined) params.set('page', String(filters.page));
  if (filters.size !== undefined) params.set('size', String(filters.size));

  const qs = params.toString();
  const response = await adminFetch(`/stations${qs ? `?${qs}` : ''}`);
  if (!response.ok) {
    throw new Error(`list_stations_failed_${response.status}`);
  }
  return (await response.json()) as StationListPage;
}

export interface StreamDetail {
  id: string;
  url: string;
  codec: string | null;
  bitrate: number | null;
  format: string | null;
  is_primary: boolean;
  status: string;
  failed_checks: number;
  last_error: string | null;
  last_check_at: string | null;
}

export interface GenreRef {
  genre_id: number;
  slug: string;
  name: string;
  confidence: number;
  source: string;
}

export interface AuditEntry {
  id: number;
  admin_email: string;
  decision: string;
  notes: string | null;
  created_at: string;
}

export interface StationDetail {
  id: string;
  slug: string;
  name: string;
  status: StationStatus;
  curated: boolean;
  country_code: string | null;
  city: string | null;
  language: string | null;
  homepage_url: string | null;
  quality_score: number;
  clickcount: number;
  votes: number;
  click_trend: string;
  failed_checks: number;
  last_error: string | null;
  last_check_at: string | null;
  last_sync_at: string | null;
  created_at: string;
  streams: StreamDetail[];
  genres: GenreRef[];
  audit: AuditEntry[];
}

export async function getStationDetail(id: string): Promise<StationDetail> {
  const response = await adminFetch(`/stations/${id}`);
  if (!response.ok) {
    if (response.status === 404) throw new Error('not_found');
    throw new Error(`get_station_failed_${response.status}`);
  }
  return (await response.json()) as StationDetail;
}

export interface StationUpdate {
  curated?: boolean;
  status?: 'active' | 'broken' | 'inactive';
  name?: string;
  slug?: string;
  genre_ids?: number[];
  notes?: string;
}

export async function updateStation(
  id: string,
  update: StationUpdate,
): Promise<StationDetail> {
  const response = await adminFetch(`/stations/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(update),
  });
  if (!response.ok) {
    if (response.status === 409) throw new Error('slug_conflict');
    if (response.status === 404) throw new Error('not_found');
    if (response.status === 400) throw new Error('invalid_payload');
    throw new Error(`update_failed_${response.status}`);
  }
  return (await response.json()) as StationDetail;
}
