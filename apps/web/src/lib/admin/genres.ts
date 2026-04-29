const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export interface GenreNode {
  id: number;
  slug: string;
  name: string;
  color_hex: string;
  parent_id: number | null;
  station_count: number;
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
