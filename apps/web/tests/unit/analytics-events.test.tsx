import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FestivalHero } from '@/components/festivals/FestivalHero';
import { pageSource, stationEventParams, trackEvent } from '@/lib/analytics';
import { usePlayerStore } from '@/lib/player-store';
import type { Festival } from '@/lib/festivals';
import type { StationSummary } from '@/lib/types';

vi.mock('next/image', () => ({
  default: ({ src, alt }: { src: string; alt: string }) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={alt} />
  ),
}));

type W = { gtag?: unknown };
const gtag = vi.fn();

beforeEach(() => {
  gtag.mockReset();
  (window as unknown as W).gtag = gtag;
});
afterEach(() => {
  delete (window as unknown as W).gtag;
  usePlayerStore.getState().stop();
});

const station: StationSummary = {
  id: 's1',
  slug: 'rave-fm',
  name: 'Rave FM',
  country_code: 'DE',
  city: null,
  curated: false,
  quality_score: 80,
  votes_local: 0,
  genres: ['techno', 'house'],
};

describe('trackEvent', () => {
  it('forwards name and params to gtag', () => {
    trackEvent('favorite_add', { station_slug: 'x', logged_in: false });
    expect(gtag).toHaveBeenCalledWith('event', 'favorite_add', { station_slug: 'x', logged_in: false });
  });

  it('is a silent no-op when GA is not loaded', () => {
    delete (window as unknown as W).gtag;
    expect(() => trackEvent('favorite_add', { station_slug: 'x', logged_in: true })).not.toThrow();
  });

  it('never throws even if gtag does', () => {
    gtag.mockImplementation(() => {
      throw new Error('boom');
    });
    expect(() => trackEvent('favorite_add', { station_slug: 'x', logged_in: true })).not.toThrow();
  });
});

describe('pageSource', () => {
  it.each([
    ['/es', 'home'],
    ['/en/', 'home'],
    ['/es/genres/techno', 'genre'],
    ['/es/countries/de/techno', 'country'],
    ['/es/stations/rave-fm', 'station'],
    ['/es/festivals/17/x', 'festival'],
    ['/es/search', 'search'],
    ['/es/trending', 'trending'],
    ['/es/favorites', 'favorites'],
    ['/es/lo-que-sea', 'other'],
  ])('%s -> %s', (path, expected) => expect(pageSource(path)).toBe(expected));
});

describe('stationEventParams', () => {
  it('uses first genre, country and page source', () => {
    expect(stationEventParams(station, '/es/genres/techno')).toEqual({
      station_slug: 'rave-fm',
      genre: 'techno',
      country: 'DE',
      source: 'genre',
    });
  });

  it('omits genre and country when unknown', () => {
    expect(stationEventParams({ slug: 'a', genres: [], country_code: null }, '/es')).toEqual({
      station_slug: 'a',
      source: 'home',
    });
  });
});

describe('play_start', () => {
  it('fires when the store starts a station, with no PII', () => {
    window.history.pushState({}, '', '/es/trending');
    usePlayerStore.getState().play(station);
    expect(gtag).toHaveBeenCalledTimes(1);
    expect(gtag).toHaveBeenCalledWith('event', 'play_start', {
      station_slug: 'rave-fm',
      genre: 'techno',
      country: 'DE',
      source: 'trending',
    });
  });

  it('does not fire on pause/toggle', () => {
    usePlayerStore.getState().play(station);
    gtag.mockClear();
    usePlayerStore.getState().pause();
    usePlayerStore.getState().toggle();
    expect(gtag).not.toHaveBeenCalled();
  });
});

describe('festival_outbound', () => {
  const festival: Festival = {
    id: '17',
    name: 'Rave on Snow',
    startDate: '2026-12-10T00:00:00.000Z',
    endDate: '2026-12-13T00:00:00.000Z',
    location: 'Saalbach',
    locationEn: null,
    countryCode: 'AT',
    website: 'https://raveonsnow.com',
    imageUrl: null,
    description: null,
    descriptionEn: null,
    genres: [],
  };
  const labels = { viewOnGofestivals: 'Ver en gofestivals', officialSite: 'Web oficial' };

  it.each([
    ['Ver en gofestivals', 'gofestivals'],
    ['Web oficial', 'official'],
  ])('click on "%s" reports destination %s', (text, destination) => {
    render(
      <FestivalHero festival={festival} locale="es" color="#fff" phaseLabel="x" phase="upcoming" countryName={null} labels={labels} />,
    );
    fireEvent.click(screen.getByText(text));
    expect(gtag).toHaveBeenCalledWith('event', 'festival_outbound', {
      festival_id: '17',
      destination,
      placement: 'hero',
    });
  });
});
