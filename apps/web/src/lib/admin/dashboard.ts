import { adminFetch } from './api';

export interface DashboardKpis {
  stations_active: number;
  stations_curated: number;
  stations_broken: number;
  avg_quality_active: number;
}

export interface QualityBucket {
  bucket: string;
  count: number;
}

export interface GenreCount {
  name: string;
  count: number;
}

export interface CountryCount {
  country_code: string;
  count: number;
}

export interface ActivityEntry {
  id: number;
  decision: string;
  station_id: string;
  station_name: string | null;
  station_slug: string | null;
  admin_email: string | null;
  notes: string | null;
  created_at: string;
}

export interface DashboardStats {
  kpis: DashboardKpis;
  quality_distribution: QualityBucket[];
  top_genres_curated: GenreCount[];
  top_countries: CountryCount[];
  recent_activity: ActivityEntry[];
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const response = await adminFetch('/dashboard/stats');
  if (!response.ok) {
    throw new Error(`stats_failed_${response.status}`);
  }
  return (await response.json()) as DashboardStats;
}
