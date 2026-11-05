import { festivalSlug as toKebab } from '@/lib/festivals';
import type { Genre } from '@/lib/types';

// Traduce los géneros de un festival de gofestivals (~410, casi todos subgéneros
// como "Melodic Techno") a los géneros que tiene la radio. Adaptado de
// `radioGenres.js` de gofestivals (RADIO-CROSSLINKS-PLAN.md): el resultado solo
// puede ser un slug de `valid`, es decir, uno que la radio tenga hoy.

// Cada entrada lista candidatos de más a menos específico: gana el primero que
// exista en la radio (`valid`). La radio tiene 20 géneros raíz y 7 subgéneros
// (minimal, hard-techno, deep-house, tech-house, progressive, psy-trance, liquid-dnb).
const ALIASES: Record<string, readonly string[]> = {
  'drum-bass': ['dnb'],
  'drum-and-bass': ['dnb'],
  'drum-n-bass': ['dnb'],
  'd-n-b': ['dnb'],
  jungle: ['dnb'],
  neurofunk: ['dnb'],
  liquid: ['liquid-dnb', 'dnb'],
  'liquid-funk': ['liquid-dnb', 'dnb'],
  'liquid-drum-bass': ['liquid-dnb', 'dnb'],
  'liquid-drum-and-bass': ['liquid-dnb', 'dnb'],
  psytrance: ['psy-trance', 'trance'],
  psy: ['psy-trance', 'trance'],
  goa: ['psy-trance', 'trance'],
  'goa-trance': ['psy-trance', 'trance'],
  'psychedelic-trance': ['psy-trance', 'trance'],
  darkpsy: ['psy-trance', 'trance'],
  'progressive-trance': ['progressive', 'trance'],
  chillout: ['chill-out'],
  chill: ['chill-out'],
  'dub-step': ['dubstep'],
  'minimal-techno': ['minimal', 'techno'],
  hardtechno: ['hard-techno', 'techno'],
  'hardcore-techno': ['hardcore'],
  gabber: ['hardcore'],
  gabba: ['hardcore'],
  oldschool: ['old-school'],
  'old-skool': ['old-school'],
  'break-beat': ['breakbeat'],
  breakbeats: ['breakbeat'],
  breaks: ['breakbeat'],
  electronica: ['electronic'],
  'electronic-music': ['electronic'],
  'electronic-dance-music': ['edm'],
  'dance-music': ['dance'],
  eurodance: ['dance'],
};

// Género padre de un subgénero, por token al final o al principio ("Acid House",
// "Techno Minimal"). Orden = prioridad: los tokens más específicos primero. Solo
// con separador de palabra, así "Frenchcore" NO cuenta como hardcore.
const PARENT_TOKENS: ReadonlyArray<readonly [string, readonly string[]]> = [
  ['psytrance', ['psy-trance', 'trance']],
  ['psy', ['psy-trance', 'trance']],
  ['electronica', ['electronic']],
  ['electronic', ['electronic']],
  ['tech-house', ['tech-house', 'house']],
  ['deep-house', ['deep-house', 'house']],
  ['hard-techno', ['hard-techno', 'techno']],
  ['techno', ['techno']],
  ['house', ['house']],
  ['trance', ['trance']],
  ['drum-bass', ['dnb']],
  ['drum-and-bass', ['dnb']],
  ['dnb', ['dnb']],
  ['dubstep', ['dubstep']],
  ['hardstyle', ['hardstyle']],
  ['hardcore', ['hardcore']],
  ['breakbeat', ['breakbeat']],
  ['ambient', ['ambient']],
  ['downtempo', ['downtempo']],
  ['electro', ['electro']],
  ['edm', ['edm']],
  ['dance', ['dance']],
];

/** Slug de la radio al que pertenece un género de festival, o null. Solo devuelve slugs de `valid`. */
export function radioSlugForGenreName(name: string, valid: ReadonlySet<string>): string | null {
  const kebab = toKebab(name);
  if (!kebab) return null;
  const candidates = [
    kebab,
    ...(ALIASES[kebab] ?? []),
    ...PARENT_TOKENS.filter(([t]) => kebab.endsWith(`-${t}`)).flatMap(([, c]) => c),
    ...PARENT_TOKENS.filter(([t]) => kebab.startsWith(`${t}-`)).flatMap(([, c]) => c),
  ];
  return candidates.find((c) => valid.has(c)) ?? null;
}

export interface GenreWeight {
  slug: string;
  count: number;
}

/**
 * Géneros de la radio de un festival con cuántos de sus géneros caen en cada uno,
 * de más a menos (empates por slug, para que sea determinista). Un festival lista
 * 10-30 géneros sin orden útil: el peso es la única señal de cuál domina.
 */
export function festivalGenreWeights(
  genreNames: readonly string[],
  valid: ReadonlySet<string>,
): GenreWeight[] {
  const counts = new Map<string, number>();
  for (const name of new Set(genreNames)) {
    const slug = radioSlugForGenreName(name, valid);
    if (slug) counts.set(slug, (counts.get(slug) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([slug, count]) => ({ slug, count }))
    .sort((a, b) => b.count - a.count || a.slug.localeCompare(b.slug));
}

/**
 * Reparte `total` huecos de emisoras entre los `maxGenres` géneros principales,
 * proporcionalmente a su peso y con al menos uno cada uno (resto mayor).
 */
export function allocateSlots(
  weights: readonly GenreWeight[],
  total: number,
  maxGenres = 3,
): GenreWeight[] {
  const top = weights.slice(0, Math.max(1, Math.min(maxGenres, total)));
  const sum = top.reduce((acc, w) => acc + w.count, 0);
  if (top.length === 0 || sum === 0) return [];
  const exact = top.map((w) => (total * w.count) / sum);
  const slots = exact.map((x) => Math.max(1, Math.floor(x)));
  let used = slots.reduce((a, b) => a + b, 0);
  while (used < total) {
    let best = 0;
    for (let i = 1; i < top.length; i++) {
      if (exact[i]! - slots[i]! > exact[best]! - slots[best]!) best = i;
    }
    slots[best]! += 1;
    used += 1;
  }
  while (used > total) {
    let worst = -1;
    for (let i = 0; i < top.length; i++) {
      if (slots[i]! > 1 && (worst === -1 || slots[i]! - exact[i]! > slots[worst]! - exact[worst]!)) worst = i;
    }
    if (worst === -1) break;
    slots[worst]! -= 1;
    used -= 1;
  }
  return top.map((w, i) => ({ slug: w.slug, count: slots[i]! }));
}

/**
 * Suma cada subgénero a su género raíz ("deep-house" cuenta como "house"). Se usa para
 * repartir emisoras: pedir `house` ya incluye sus subgéneros, y así los 3 géneros
 * principales son raíces distintas en vez de un padre y sus hijos.
 */
export function rollUpToRoots(
  weights: readonly GenreWeight[],
  bySlug: Record<string, Genre>,
): GenreWeight[] {
  const byId = new Map(Object.values(bySlug).map((g) => [g.id, g]));
  const rootOf = (g: Genre): Genre => {
    let cur = g;
    for (let i = 0; i < 10 && cur.parent_id !== null; i++) {
      const parent = byId.get(cur.parent_id);
      if (!parent) break;
      cur = parent;
    }
    return cur;
  };
  const counts = new Map<string, number>();
  for (const w of weights) {
    const genre = bySlug[w.slug];
    const root = genre ? rootOf(genre).slug : w.slug;
    counts.set(root, (counts.get(root) ?? 0) + w.count);
  }
  return [...counts.entries()]
    .map(([slug, count]) => ({ slug, count }))
    .sort((a, b) => b.count - a.count || a.slug.localeCompare(b.slug));
}
