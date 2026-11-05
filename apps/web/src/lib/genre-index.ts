import type { Genre } from '@/lib/types';

/** Índice slug → género de todo el árbol (raíces y subgéneros). */
export function indexGenresBySlug(genres: Genre[]): Record<string, Genre> {
  const out: Record<string, Genre> = {};
  const walk = (g: Genre) => {
    out[g.slug] = g;
    g.children.forEach(walk);
  };
  genres.forEach(walk);
  return out;
}
