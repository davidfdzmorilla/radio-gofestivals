import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  __resetSessionStateForTests,
  markSessionEnded,
  setStoredToken,
  tryRefreshSession,
} from '@/lib/users/api';

const HINT_KEY = 'rgf_session_hint';

function refreshResponse(status: number): Response {
  if (status !== 200) {
    return new Response(JSON.stringify({ detail: 'x' }), { status });
  }
  return new Response(
    JSON.stringify({ access_token: 'jwt', user: { id: 'u' } }),
    { status: 200, headers: { 'Content-Type': 'application/json' } },
  );
}

describe('session hint (evita el 401 de /auth/refresh en cada carga anónima)', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    __resetSessionStateForTests();
    fetchSpy = vi.spyOn(globalThis, 'fetch');
  });

  afterEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
  });

  it('asks the server once when there is no hint, then stops after a 401', async () => {
    fetchSpy.mockResolvedValue(refreshResponse(401));

    expect(await tryRefreshSession()).toBeNull();
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(window.localStorage.getItem(HINT_KEY)).toBe('0');

    expect(await tryRefreshSession()).toBeNull();
    expect(fetchSpy).toHaveBeenCalledTimes(1); // sin segunda petición
  });

  it('never calls the server while the hint says there is no session', async () => {
    window.localStorage.setItem(HINT_KEY, '0');

    expect(await tryRefreshSession()).toBeNull();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('still refreshes when the hint says there is a session', async () => {
    window.localStorage.setItem(HINT_KEY, '1');
    fetchSpy.mockResolvedValue(refreshResponse(200));

    const session = await tryRefreshSession();

    expect(session?.accessToken).toBe('jwt');
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(window.localStorage.getItem(HINT_KEY)).toBe('1');
  });

  it('self-heals: an expired cookie (401) flips the hint to no-session', async () => {
    window.localStorage.setItem(HINT_KEY, '1');
    fetchSpy.mockResolvedValue(refreshResponse(401));

    expect(await tryRefreshSession()).toBeNull();
    expect(window.localStorage.getItem(HINT_KEY)).toBe('0');
  });

  it.each([429, 500, 503])(
    'a transient %i does not mark the session as ended',
    async (status) => {
      window.localStorage.setItem(HINT_KEY, '1');
      fetchSpy.mockResolvedValue(refreshResponse(status));

      expect(await tryRefreshSession()).toBeNull();
      expect(window.localStorage.getItem(HINT_KEY)).toBe('1');
    },
  );

  it('a network error does not mark the session as ended', async () => {
    window.localStorage.setItem(HINT_KEY, '1');
    fetchSpy.mockRejectedValue(new TypeError('network'));

    expect(await tryRefreshSession()).toBeNull();
    expect(window.localStorage.getItem(HINT_KEY)).toBe('1');
  });

  it('login re-enables refresh and logout disables it again', async () => {
    window.localStorage.setItem(HINT_KEY, '0');

    setStoredToken('jwt'); // login
    expect(window.localStorage.getItem(HINT_KEY)).toBe('1');

    markSessionEnded(); // logout
    expect(window.localStorage.getItem(HINT_KEY)).toBe('0');
    expect(await tryRefreshSession()).toBeNull();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('keeps asking the server when localStorage is unavailable', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    fetchSpy.mockResolvedValue(refreshResponse(401));

    expect(await tryRefreshSession()).toBeNull();
    expect(await tryRefreshSession()).toBeNull();
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });
});
