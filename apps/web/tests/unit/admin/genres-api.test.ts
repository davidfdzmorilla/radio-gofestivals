import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  type GenreNode,
  flattenGenres,
  listAllGenres,
} from '@/lib/admin/genres';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('listAllGenres', () => {
  it('GETs /api/v1/genres and returns the tree', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: 1,
            slug: 'techno',
            name: 'Techno',
            color_hex: '#000',
            parent_id: null,
            station_count: 10,
            children: [],
          },
        ]),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    const result = await listAllGenres();
    expect(result).toHaveLength(1);
    expect(result[0]!.slug).toBe('techno');
    const fetchSpy = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    expect(fetchSpy.mock.calls[0]![0]).toBe(`${API_BASE}/api/v1/genres`);
  });

  it('throws on non-2xx', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 500 }),
    );
    await expect(listAllGenres()).rejects.toThrow(
      'fetch_genres_failed_500',
    );
  });
});

describe('flattenGenres', () => {
  const tree: GenreNode[] = [
    {
      id: 1,
      slug: 'techno',
      name: 'Techno',
      color_hex: '#000',
      parent_id: null,
      station_count: 0,
      children: [
        {
          id: 13,
          slug: 'minimal',
          name: 'Minimal Techno',
          color_hex: '#000',
          parent_id: 1,
          station_count: 0,
          children: [],
        },
      ],
    },
    {
      id: 2,
      slug: 'house',
      name: 'House',
      color_hex: '#000',
      parent_id: null,
      station_count: 0,
      children: [],
    },
  ];

  it('flattens parent → children → next parent order', () => {
    const flat = flattenGenres(tree);
    expect(flat.map((n) => n.slug)).toEqual(['techno', 'minimal', 'house']);
  });

  it('annotates depth correctly', () => {
    const flat = flattenGenres(tree);
    expect(flat.find((n) => n.slug === 'techno')!.depth).toBe(0);
    expect(flat.find((n) => n.slug === 'minimal')!.depth).toBe(1);
    expect(flat.find((n) => n.slug === 'house')!.depth).toBe(0);
  });

  it('handles empty array', () => {
    expect(flattenGenres([])).toEqual([]);
  });
});
