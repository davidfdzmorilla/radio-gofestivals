import { adminFetch } from './api';

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export interface GenreNode {
  id: number;
  slug: string;
  name: string;
  color_hex: string;
  parent_id: number | null;
  station_count: number;
  // Public /api/v1/genres only returns the fields above. The admin
  // mutation endpoints return sort_order/description as well, and the
  // edit modal needs them, so we widen the type with optionals.
  sort_order?: number;
  description?: string | null;
  children?: GenreNode[];
}

export interface FlatGenre extends Omit<GenreNode, 'children'> {
  depth: number;
}

/**
 * Reuses the public /api/v1/genres endpoint (read-only, no auth needed).
 * Returns the hierarchical genre tree.
 */
export async function listAllGenres(): Promise<GenreNode[]> {
  const response = await fetch(`${API_BASE}/api/v1/genres`);
  if (!response.ok) {
    throw new Error(`fetch_genres_failed_${response.status}`);
  }
  return (await response.json()) as GenreNode[];
}

/**
 * Flattens the hierarchical tree into an ordered list. Parents appear
 * before each of their children. Each node is annotated with its depth
 * so callers can render indentation.
 */
export function flattenGenres(tree: GenreNode[]): FlatGenre[] {
  const out: FlatGenre[] = [];
  const visit = (nodes: GenreNode[], depth: number) => {
    for (const node of nodes) {
      const { children, ...rest } = node;
      out.push({ ...rest, depth });
      if (children && children.length > 0) {
        visit(children, depth + 1);
      }
    }
  };
  visit(tree, 0);
  return out;
}

// ---------------------------------------------------------------------------
// Admin mutations (require Bearer token)
// ---------------------------------------------------------------------------

export interface GenreOut {
  id: number;
  slug: string;
  name: string;
  parent_id: number | null;
  color_hex: string;
  sort_order: number;
  description: string | null;
}

export interface GenreCreate {
  slug: string;
  name: string;
  parent_id?: number | null;
  color_hex?: string;
  sort_order?: number;
  description?: string | null;
}

export interface GenreUpdate {
  slug?: string;
  name?: string;
  parent_id?: number | null;
  color_hex?: string;
  sort_order?: number;
  description?: string | null;
}

export async function createGenre(data: GenreCreate): Promise<GenreOut> {
  const response = await adminFetch('/genres', {
    method: 'POST',
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    if (response.status === 409) throw new Error('slug_conflict');
    if (response.status === 400) throw new Error('invalid_payload');
    throw new Error(`create_failed_${response.status}`);
  }
  return (await response.json()) as GenreOut;
}

export async function updateGenre(
  id: number,
  data: GenreUpdate,
): Promise<GenreOut> {
  const response = await adminFetch(`/genres/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    if (response.status === 409) throw new Error('slug_conflict');
    if (response.status === 404) throw new Error('not_found');
    if (response.status === 400) throw new Error('invalid_payload');
    throw new Error(`update_failed_${response.status}`);
  }
  return (await response.json()) as GenreOut;
}

export async function deleteGenre(id: number): Promise<void> {
  const response = await adminFetch(`/genres/${id}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    if (response.status === 409) throw new Error('genre_in_use');
    if (response.status === 404) throw new Error('not_found');
    throw new Error(`delete_failed_${response.status}`);
  }
}
