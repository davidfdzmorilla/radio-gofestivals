import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  adminFetch,
  clearToken,
  getStoredToken,
  storeToken,
} from '@/lib/admin/api';
import { isAuthenticated, login, LoginError } from '@/lib/admin/auth';

const originalLocation = window.location;

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: originalLocation,
  });
});

describe('admin token helpers', () => {
  it('storeToken/getStoredToken/clearToken roundtrip', () => {
    expect(getStoredToken()).toBeNull();
    storeToken('abc.def.ghi');
    expect(getStoredToken()).toBe('abc.def.ghi');
    clearToken();
    expect(getStoredToken()).toBeNull();
  });

  it('isAuthenticated reflects token presence', () => {
    expect(isAuthenticated()).toBe(false);
    storeToken('t');
    expect(isAuthenticated()).toBe(true);
    clearToken();
    expect(isAuthenticated()).toBe(false);
  });
});

describe('adminFetch', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
  });

  it('attaches Authorization header when token is stored', async () => {
    storeToken('jwt-1');
    await adminFetch('/auth/me');
    const fetchSpy = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    const init = fetchSpy.mock.calls[0]![1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer jwt-1');
  });

  it('omits Authorization when skipAuth=true', async () => {
    storeToken('jwt-1');
    await adminFetch('/auth/login', { method: 'POST', skipAuth: true });
    const fetchSpy = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    const init = fetchSpy.mock.calls[0]![1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
  });

  it('clears token and redirects to /admin/login on 401', async () => {
    storeToken('jwt-bad');
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...originalLocation, href: '' },
    });
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      new Response('', { status: 401 }),
    );
    await adminFetch('/auth/me');
    expect(getStoredToken()).toBeNull();
    expect(window.location.href).toBe('/admin/login');
  });

  it('does NOT redirect on 401 when skipAuth=true (login flow)', async () => {
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...originalLocation, href: 'untouched' },
    });
    (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      new Response('', { status: 401 }),
    );
    const resp = await adminFetch('/auth/login', {
      method: 'POST',
      skipAuth: true,
    });
    expect(resp.status).toBe(401);
    expect(window.location.href).toBe('untouched');
  });
});

describe('login()', () => {
  it('stores token and returns payload on success', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: 'jwt-x',
          token_type: 'bearer',
          expires_at: '2026-04-29T00:00:00Z',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    const result = await login('a@b.com', 'pw');
    expect(result.access_token).toBe('jwt-x');
    expect(getStoredToken()).toBe('jwt-x');
  });

  it('throws LoginError("invalid_credentials") on 401', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 401 }),
    );
    await expect(login('a@b.com', 'pw')).rejects.toThrow(LoginError);
    await expect(login('a@b.com', 'pw')).rejects.toMatchObject({
      code: 'invalid_credentials',
    });
  });

  it('throws LoginError("rate_limit_exceeded") on 429', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 429 }),
    );
    await expect(login('a@b.com', 'pw')).rejects.toMatchObject({
      code: 'rate_limit_exceeded',
    });
  });
});
