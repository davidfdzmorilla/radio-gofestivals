import { describe, expect, it } from 'vitest';
import {
  allocateSlots,
  festivalGenreWeights,
  radioSlugForGenreName,
  rollUpToRoots,
} from '@/lib/festival-genres';
import type { Genre } from '@/lib/types';

// Árbol real de la radio (2026-11-05): 20 géneros raíz y 7 subgéneros.
const ROOTS = [
  'techno', 'house', 'trance', 'dnb', 'electronic', 'breakbeat', 'electro', 'edm',
  'dubstep', 'hardstyle', 'ambient', 'hardcore', 'dance', 'downtempo', 'chill-out',
  'makina', 'noise', 'old-school', 'schranz', 'uptempo',
];
const CHILDREN: Array<[string, string]> = [
  ['minimal', 'techno'], ['hard-techno', 'techno'], ['deep-house', 'house'],
  ['tech-house', 'house'], ['progressive', 'trance'], ['psy-trance', 'trance'],
  ['liquid-dnb', 'dnb'],
];
const TREE: Record<string, Genre> = {};
ROOTS.forEach((slug, i) => {
  TREE[slug] = { id: i + 1, slug, name: slug, color_hex: '#fff', parent_id: null, station_count: 0, children: [] };
});
CHILDREN.forEach(([slug, parent], i) => {
  TREE[slug] = { id: 100 + i, slug, name: slug, color_hex: '#fff', parent_id: TREE[parent]!.id, station_count: 0, children: [] };
});
const VALID = new Set(Object.keys(TREE));

describe('radioSlugForGenreName', () => {
  it.each([
    ['Techno', 'techno'],
    ['Melodic Techno', 'techno'],
    ['Hard Techno', 'hard-techno'],
    ['Minimal Techno', 'minimal'],
    ['Minimal', 'minimal'],
    ['Deep House', 'deep-house'],
    ['Tech House', 'tech-house'],
    ['Progressive House', 'house'],
    ['Acid House', 'house'],
    ['Drum & Bass', 'dnb'],
    ['Drum And Bass', 'dnb'],
    ['Liquid Funk', 'liquid-dnb'],
    ['Liquid Drum & Bass', 'liquid-dnb'],
    ['Jungle', 'dnb'],
    ['Psytrance', 'psy-trance'],
    ['Dark Psytrance', 'psy-trance'],
    ['Goa Trance', 'psy-trance'],
    ['Chillout', 'chill-out'],
    ['Jazz Electronic', 'electronic'],
    ['Future House', 'house'],
    ['Gabber', 'hardcore'],
    ['Happy Hardcore', 'hardcore'],
    ['Breakbeat', 'breakbeat'],
    ['  TECHNO  ', 'techno'],
  ])('%s -> %s', (name, expected) => {
    expect(radioSlugForGenreName(name, VALID)).toBe(expected);
  });

  it.each(['Hip Hop', 'Reggae', 'Disco', 'Hyperpop', 'Frenchcore', '', '★★★'])(
    'returns null for %j (no radio genre)',
    (name) => {
      expect(radioSlugForGenreName(name, VALID)).toBeNull();
    },
  );

  it('never returns a slug the radio does not have: it falls back to the parent genre', () => {
    const rootsOnly = new Set(ROOTS);
    expect(radioSlugForGenreName('Deep House', rootsOnly)).toBe('house');
    expect(radioSlugForGenreName('Hard Techno', rootsOnly)).toBe('techno');
    expect(radioSlugForGenreName('Psytrance', rootsOnly)).toBe('trance');
    expect(radioSlugForGenreName('Liquid Funk', rootsOnly)).toBe('dnb');
    expect(radioSlugForGenreName('Melodic Techno', new Set(['house']))).toBeNull();
  });
});

describe('festivalGenreWeights', () => {
  it('counts distinct festival genres per radio genre, most frequent first', () => {
    // Rave on Snow Festival (datos reales de la API).
    const names = [
      'Hard Techno', 'House', 'Techno', 'Deep House', 'Drum And Bass', 'Tech House',
      'Melodic Techno', 'Acid Techno', 'Progressive House', 'Minimal Techno',
    ];
    expect(festivalGenreWeights(names, VALID)).toEqual([
      // Techno, Melodic Techno y Acid Techno caen en `techno`; House y Progressive House en `house`.
      { slug: 'techno', count: 3 },
      { slug: 'house', count: 2 },
      { slug: 'deep-house', count: 1 },
      { slug: 'dnb', count: 1 },
      { slug: 'hard-techno', count: 1 },
      { slug: 'minimal', count: 1 },
      { slug: 'tech-house', count: 1 },
    ]);
  });

  it('ignores duplicates and genres without a radio equivalent', () => {
    expect(festivalGenreWeights(['Techno', 'Techno', 'Hip Hop', 'Reggae'], VALID)).toEqual([
      { slug: 'techno', count: 1 },
    ]);
    expect(festivalGenreWeights([], VALID)).toEqual([]);
  });

  it('is deterministic on ties', () => {
    expect(festivalGenreWeights(['Trance', 'House', 'Techno'], VALID).map((w) => w.slug)).toEqual([
      'house', 'techno', 'trance',
    ]);
  });
});

describe('allocateSlots', () => {
  it('splits the slots proportionally with at least one per genre and the exact total', () => {
    const out = allocateSlots(
      [{ slug: 'techno', count: 5 }, { slug: 'house', count: 4 }, { slug: 'dnb', count: 1 }],
      6,
    );
    expect(out.map((o) => o.count).reduce((a, b) => a + b, 0)).toBe(6);
    expect(out.every((o) => o.count >= 1)).toBe(true);
    expect(out.map((o) => o.slug)).toEqual(['techno', 'house', 'dnb']);
    expect(out[0]!.count).toBeGreaterThanOrEqual(out[1]!.count);
  });

  it('gives all the slots to a single genre', () => {
    expect(allocateSlots([{ slug: 'techno', count: 3 }], 6)).toEqual([{ slug: 'techno', count: 6 }]);
  });

  it('only considers the top 3 genres', () => {
    const w = ['a', 'b', 'c', 'd', 'e'].map((slug, i) => ({ slug, count: 5 - i }));
    expect(allocateSlots(w, 6).map((o) => o.slug)).toEqual(['a', 'b', 'c']);
  });

  it('returns nothing when there are no genres', () => {
    expect(allocateSlots([], 6)).toEqual([]);
  });

  it.each([1, 2, 3, 6, 8])('always adds up to %i (or the number of genres if larger)', (total) => {
    const w = [{ slug: 'a', count: 7 }, { slug: 'b', count: 2 }, { slug: 'c', count: 1 }];
    const sum = allocateSlots(w, total).reduce((acc, o) => acc + o.count, 0);
    expect(sum).toBe(total);
  });
});

describe('rollUpToRoots', () => {
  it('adds each subgenre to its root so the top genres are distinct roots', () => {
    // Rave on Snow Festival con el árbol real: antes top-3 = techno, house, deep-house.
    const names = [
      'Hard Techno', 'House', 'Techno', 'Deep House', 'Drum And Bass', 'Tech House',
      'Melodic Techno', 'Acid Techno', 'Progressive House', 'Minimal Techno',
    ];
    const rolled = rollUpToRoots(festivalGenreWeights(names, VALID), TREE);
    expect(rolled).toEqual([
      // techno 3 + hard-techno 1 + minimal 1; house 2 + deep-house 1 + tech-house 1.
      { slug: 'techno', count: 5 },
      { slug: 'house', count: 4 },
      { slug: 'dnb', count: 1 },
    ]);
  });

  it('keeps unknown slugs as they are and preserves the total', () => {
    const rolled = rollUpToRoots([{ slug: 'deep-house', count: 2 }, { slug: 'ghost', count: 3 }], TREE);
    expect(rolled).toEqual([{ slug: 'ghost', count: 3 }, { slug: 'house', count: 2 }]);
    expect(rolled.reduce((a, w) => a + w.count, 0)).toBe(5);
  });

  it('a root genre counts for itself', () => {
    expect(rollUpToRoots([{ slug: 'techno', count: 1 }], TREE)).toEqual([{ slug: 'techno', count: 1 }]);
  });
});
