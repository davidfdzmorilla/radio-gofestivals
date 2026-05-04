import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { HeartButton } from '@/components/auth/HeartButton';
import { TestProviders } from './test-utils';
import { LocalStorageFavorites } from '@/lib/users/favorites';

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    refresh: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(''),
  usePathname: () => '/',
}));

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
  LocalStorageFavorites.clear();
});

describe('<HeartButton />', () => {
  it('toggles state on click for an anonymous user', async () => {
    render(
      <TestProviders>
        <HeartButton stationId="abc" />
      </TestProviders>,
    );
    const btn = await screen.findByRole('button');
    expect(btn).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(btn);
    await waitFor(() => {
      expect(btn).toHaveAttribute('aria-pressed', 'true');
    });
    // Persisted to localStorage
    const fav = new LocalStorageFavorites();
    expect(fav.has('abc')).toBe(true);
  });

  it('reverts when the backend provider call fails', async () => {
    // Authenticated user → BackendFavorites is the active provider; we
    // make /favorites/{id} fail so the optimistic add() throws.
    window.localStorage.setItem('user_token', 'jwt-1');
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input);
      const method = (init?.method ?? 'GET').toUpperCase();
      if (url.endsWith('/api/v1/auth/me')) {
        return new Response(
          JSON.stringify({
            id: 'u',
            email: 'me@x.com',
            username: null,
            display_name: null,
            bio: null,
            avatar_url: null,
            is_public: false,
            created_at: '2026-04-30T00:00:00Z',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        );
      }
      if (url.endsWith('/api/v1/favorites')) {
        return new Response(
          JSON.stringify({ items: [], total: 0 }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        );
      }
      if (url.includes('/api/v1/favorites/') && method === 'POST') {
        return new Response('', { status: 500 });
      }
      return new Response('', { status: 404 });
    });
    render(
      <TestProviders>
        <HeartButton stationId="zzz" />
      </TestProviders>,
    );
    const btn = await screen.findByRole('button');
    await waitFor(() => {
      expect(btn).toHaveAttribute('aria-pressed', 'false');
    });
    fireEvent.click(btn);
    await waitFor(() => {
      expect(btn).toHaveAttribute('aria-pressed', 'false');
    });
  });
});
