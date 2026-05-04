import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { LocalStorageFavorites } from '@/lib/users/favorites';

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  LocalStorageFavorites.clear();
});

describe('LocalStorageFavorites', () => {
  it('has() reflects add/remove', async () => {
    const fav = new LocalStorageFavorites();
    expect(fav.has('a')).toBe(false);
    await fav.add('a');
    expect(fav.has('a')).toBe(true);
    await fav.remove('a');
    expect(fav.has('a')).toBe(false);
  });

  it('add is idempotent', async () => {
    const fav = new LocalStorageFavorites();
    await fav.add('a');
    await fav.add('a');
    expect(fav.ids()).toEqual(['a']);
  });

  it('persists across instances via localStorage', async () => {
    const f1 = new LocalStorageFavorites();
    await f1.add('x');
    await f1.add('y');
    const f2 = new LocalStorageFavorites();
    expect(new Set(f2.ids())).toEqual(new Set(['x', 'y']));
  });

  it('clear() empties everything', async () => {
    const fav = new LocalStorageFavorites();
    await fav.add('z');
    LocalStorageFavorites.clear();
    const fresh = new LocalStorageFavorites();
    expect(fresh.ids()).toEqual([]);
  });

  it('remove on missing id is a no-op', async () => {
    const fav = new LocalStorageFavorites();
    await fav.remove('missing');
    expect(fav.ids()).toEqual([]);
  });
});
