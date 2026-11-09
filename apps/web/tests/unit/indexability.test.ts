import { describe, expect, it } from 'vitest';
import {
  isComboIndexable,
  isCountryIndexable,
  isGenreIndexable,
  isStationIndexable,
  NOINDEX_FOLLOW,
  robotsFor,
  STATION_INDEX_ALLOWLIST,
  stationRobotsFor,
  type StationIndexInput,
} from '@/lib/indexability';

const good: StationIndexInput = {
  slug: 'good',
  logo_hash: 'abc',
  country_code: 'DE',
  genreCount: 1,
  quality_score: 50,
};

describe('umbrales de listados', () => {
  it.each([[7, false], [8, true]])('género con %i emisoras -> %s', (n, ok) =>
    expect(isGenreIndexable(n)).toBe(ok));
  it.each([[4, false], [5, true]])('país con %i emisoras -> %s', (n, ok) =>
    expect(isCountryIndexable(n)).toBe(ok));
  it.each([[4, false], [5, true]])('país×género con %i emisoras -> %s', (n, ok) =>
    expect(isComboIndexable(n)).toBe(ok));
});

describe('isStationIndexable', () => {
  it('acepta una emisora con logo, país, género y calidad >= 50', () => {
    expect(isStationIndexable(good)).toBe(true);
  });

  it.each([
    ['sin logo', { logo_hash: null }],
    ['sin país', { country_code: null }],
    ['sin género', { genreCount: 0 }],
    ['calidad 49', { quality_score: 49 }],
  ])('rechaza %s', (_n, over) => {
    expect(isStationIndexable({ ...good, ...over })).toBe(false);
  });

  it('la allowlist salta calidad y logo', () => {
    expect(
      isStationIndexable({ ...good, slug: 'radio-onimai', logo_hash: null, quality_score: 10 }),
    ).toBe(true);
  });

  it('la allowlist NO salta la ocultación del clasificador', () => {
    for (const slug of STATION_INDEX_ALLOWLIST) {
      expect(isStationIndexable({ ...good, slug, hidden: true })).toBe(false);
    }
  });
});

describe('robots', () => {
  it('indexable -> sin directiva; no indexable -> noindex, follow', () => {
    expect(robotsFor(true)).toBeUndefined();
    expect(robotsFor(false)).toEqual({ index: false, follow: true });
    expect(NOINDEX_FOLLOW).toEqual({ index: false, follow: true });
  });

  it('ficha: oculta -> noindex,nofollow; floja -> noindex,follow; buena -> nada', () => {
    expect(stationRobotsFor({ ...good, hidden: true })).toEqual({ index: false, follow: false });
    expect(stationRobotsFor({ ...good, quality_score: 10 })).toEqual({ index: false, follow: true });
    expect(stationRobotsFor(good)).toBeUndefined();
  });
});
