import {
  FavoriteOutSchema,
  FavoritesListResponseSchema,
  MigrateFavoritesResponseSchema,
  type FavoriteOut,
  type MigrateFavoritesResponse,
} from './types';
import { userFetch } from './api';

const LS_KEY = 'anon_favorites_v1';

export interface FavoritesProvider {
  list(): Promise<FavoriteOut[]>;
  has(stationId: string): boolean;
  add(stationId: string): Promise<void>;
  remove(stationId: string): Promise<void>;
  ids(): string[];
}

// ---------------------------------------------------------------------------
// LocalStorage provider — anonymous users
// ---------------------------------------------------------------------------

interface LocalFavorite {
  station_id: string;
  added_at: string;
}

function readLocal(): LocalFavorite[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(LS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(
        (x): x is LocalFavorite =>
          typeof x === 'object'
          && x !== null
          && typeof (x as LocalFavorite).station_id === 'string',
      )
      .map((x) => ({
        station_id: x.station_id,
        added_at: x.added_at ?? new Date().toISOString(),
      }));
  } catch {
    return [];
  }
}

function writeLocal(items: LocalFavorite[]): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(LS_KEY, JSON.stringify(items));
}

export class LocalStorageFavorites implements FavoritesProvider {
  private cache: Set<string>;

  constructor() {
    this.cache = new Set(readLocal().map((it) => it.station_id));
  }

  async list(): Promise<FavoriteOut[]> {
    // LocalStorage doesn't store station summary fields; we fall back
    // to fetching the live station list filtered by id.
    const ids = readLocal().map((it) => it.station_id);
    if (ids.length === 0) return [];
    return enrichLocalIds(ids);
  }

  has(stationId: string): boolean {
    return this.cache.has(stationId);
  }

  async add(stationId: string): Promise<void> {
    if (this.cache.has(stationId)) return;
    const items = readLocal();
    items.push({
      station_id: stationId,
      added_at: new Date().toISOString(),
    });
    writeLocal(items);
    this.cache.add(stationId);
  }

  async remove(stationId: string): Promise<void> {
    if (!this.cache.has(stationId)) return;
    const items = readLocal().filter(
      (it) => it.station_id !== stationId,
    );
    writeLocal(items);
    this.cache.delete(stationId);
  }

  ids(): string[] {
    return Array.from(this.cache);
  }

  static clear(): void {
    if (typeof window === 'undefined') return;
    window.localStorage.removeItem(LS_KEY);
  }
}

async function enrichLocalIds(ids: string[]): Promise<FavoriteOut[]> {
  // Best effort: hit the public stations endpoint per id. For the MVP
  // an anonymous favorites list with N items issues N requests in
  // parallel — N is bounded by realistic user behavior (usually <20).
  const results = await Promise.all(
    ids.map(async (id) => {
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL ?? ''}/api/v1/stations?size=1&q=${id}`,
        );
        if (!res.ok) return null;
        const body = (await res.json()) as { items: unknown[] };
        const item = body.items?.[0];
        if (!item) return null;
        return mapStationItemToFavorite(item);
      } catch {
        return null;
      }
    }),
  );
  return results.filter((x): x is FavoriteOut => x !== null);
}

function mapStationItemToFavorite(raw: unknown): FavoriteOut | null {
  try {
    const it = raw as Record<string, unknown>;
    return FavoriteOutSchema.parse({
      station_id: it.id,
      slug: it.slug,
      name: it.name,
      country_code: it.country_code,
      city: it.city,
      curated: it.curated,
      quality_score: it.quality_score,
      status: 'active',
      primary_stream: it.primary_stream ?? null,
      created_at: new Date().toISOString(),
    });
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Backend provider — authenticated users
// ---------------------------------------------------------------------------

export class BackendFavorites implements FavoritesProvider {
  private cache: Set<string>;
  private hydrated: Promise<void> | null = null;

  constructor(initialIds: string[] = []) {
    this.cache = new Set(initialIds);
  }

  /** Replace the local cache with the backend's authoritative list. */
  async hydrate(): Promise<FavoriteOut[]> {
    const items = await this.list();
    this.cache = new Set(items.map((it) => it.station_id));
    return items;
  }

  async list(): Promise<FavoriteOut[]> {
    const response = await userFetch('/api/v1/favorites');
    if (!response.ok) {
      throw new Error(`favorites_list_failed_${response.status}`);
    }
    const parsed = FavoritesListResponseSchema.parse(await response.json());
    return parsed.items;
  }

  has(stationId: string): boolean {
    return this.cache.has(stationId);
  }

  async add(stationId: string): Promise<void> {
    const response = await userFetch(
      `/api/v1/favorites/${stationId}`,
      { method: 'POST' },
    );
    if (!response.ok) {
      throw new Error(`favorites_add_failed_${response.status}`);
    }
    this.cache.add(stationId);
  }

  async remove(stationId: string): Promise<void> {
    const response = await userFetch(
      `/api/v1/favorites/${stationId}`,
      { method: 'DELETE' },
    );
    if (!response.ok && response.status !== 404) {
      throw new Error(`favorites_remove_failed_${response.status}`);
    }
    this.cache.delete(stationId);
  }

  async migrate(
    stationIds: string[],
  ): Promise<MigrateFavoritesResponse> {
    if (stationIds.length === 0) {
      return { added: 0, already_existed: 0, invalid: 0 };
    }
    const response = await userFetch('/api/v1/favorites/migrate', {
      method: 'POST',
      body: JSON.stringify({ station_ids: stationIds }),
    });
    if (!response.ok) {
      throw new Error(`favorites_migrate_failed_${response.status}`);
    }
    const result = MigrateFavoritesResponseSchema.parse(
      await response.json(),
    );
    // Hydrate cache so subsequent .has() calls are correct.
    await this.hydrate();
    return result;
  }

  ids(): string[] {
    return Array.from(this.cache);
  }
}
