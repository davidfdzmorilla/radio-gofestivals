import { describe, expect, it } from 'vitest';
import { stationLogoUrl } from '@/lib/logo';

describe('stationLogoUrl', () => {
  it('points to the API logo endpoint with size and version', () => {
    const url = new URL(stationLogoUrl('radio-a', 'abc123def456', 'sm'));
    expect(url.pathname).toBe('/api/v1/stations/radio-a/logo');
    expect(url.searchParams.get('size')).toBe('sm');
    expect(url.searchParams.get('v')).toBe('abc123def456');
  });

  it('a new logo changes the URL (immutable caching never serves a stale one)', () => {
    expect(stationLogoUrl('radio-a', 'aaaaaaaaaaaa', 'lg')).not.toBe(
      stationLogoUrl('radio-a', 'bbbbbbbbbbbb', 'lg'),
    );
    expect(stationLogoUrl('radio-a', 'aaaaaaaaaaaa', 'sm')).not.toBe(
      stationLogoUrl('radio-a', 'aaaaaaaaaaaa', 'lg'),
    );
  });

  it('encodes the slug and the version so they cannot break out of the URL', () => {
    const url = new URL(stationLogoUrl('a/b?c#d', 'x&y=z', 'sm'));
    expect(url.pathname).toBe('/api/v1/stations/a%2Fb%3Fc%23d/logo');
    expect(url.searchParams.get('v')).toBe('x&y=z');
    expect(url.searchParams.get('y')).toBeNull();
    expect(url.hash).toBe('');
  });
});
