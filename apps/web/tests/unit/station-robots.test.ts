import { describe, expect, it } from 'vitest';
import { stationRobots } from '@/lib/seo';
import { StationDetailSchema } from '@/lib/types';

describe('stationRobots', () => {
  it('marks hidden stations noindex, nofollow', () => {
    expect(stationRobots(true)).toEqual({ index: false, follow: false });
  });

  it('declares nothing for visible stations', () => {
    expect(stationRobots(false)).toBeUndefined();
  });
});

describe('StationDetailSchema.hidden', () => {
  const base = {
    id: 'x', slug: 's', name: 'S', homepage_url: null, country_code: null, city: null,
    language: null, curated: false, quality_score: 1, status: 'active', genres: [],
    now_playing: [],
  };

  it('defaults to false when an older cached payload lacks it', () => {
    expect(StationDetailSchema.parse(base).hidden).toBe(false);
  });

  it('keeps hidden = true from the API', () => {
    expect(StationDetailSchema.parse({ ...base, hidden: true }).hidden).toBe(true);
  });
});
