import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  forgotPassword,
  loginUser,
  registerUser,
  resetPassword,
} from '@/lib/users/auth';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe('registerUser', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          user: {
            id: 'a',
            email: 'a@b.com',
            username: null,
            display_name: null,
            bio: null,
            avatar_url: null,
            is_public: false,
            created_at: '2026-04-30T00:00:00Z',
          },
          access_token: 'jwt',
          token_type: 'bearer',
          expires_at: '2026-05-30T00:00:00Z',
        }),
        {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        },
      ),
    );
  });

  it('POSTs /auth/register with skipAuth body', async () => {
    const result = await registerUser('a@b.com', 'pw1234567');
    expect(result.access_token).toBe('jwt');
    const fetchSpy = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    const [url, init] = fetchSpy.mock.calls[0]!;
    expect(String(url)).toBe(`${API_BASE}/api/v1/auth/register`);
    expect((init as RequestInit).method).toBe('POST');
    const headers = (init as RequestInit).headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
  });

  it('maps 400 email_already_registered to email_already_exists', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ detail: 'email_already_registered' }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        },
      ),
    );
    await expect(registerUser('a@b.com', 'pw1234567')).rejects.toThrow(
      'email_already_exists',
    );
  });

  it('maps 422 to invalid_payload', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 422 }),
    );
    await expect(registerUser('a@b.com', 'short')).rejects.toThrow(
      'invalid_payload',
    );
  });

  it('maps 429 to rate_limit_exceeded', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 429 }),
    );
    await expect(registerUser('a@b.com', 'pw1234567')).rejects.toThrow(
      'rate_limit_exceeded',
    );
  });
});

describe('loginUser', () => {
  it('maps 401 to invalid_credentials', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 401 }),
    );
    await expect(loginUser('a@b.com', 'pw')).rejects.toThrow(
      'invalid_credentials',
    );
  });
});

describe('forgotPassword + resetPassword', () => {
  it('forgotPassword POST with skipAuth', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    await forgotPassword('a@b.com');
    const fetchSpy = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    expect(String(fetchSpy.mock.calls[0]![0])).toBe(
      `${API_BASE}/api/v1/auth/forgot-password`,
    );
  });

  it('resetPassword 400 → invalid_or_expired_token', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 400 }),
    );
    await expect(
      resetPassword('uuid', 'newpass1234'),
    ).rejects.toThrow('invalid_or_expired_token');
  });
});
