import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { HeaderAuth } from '@/components/auth/HeaderAuth';
import { TestProviders } from './test-utils';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(''),
  usePathname: () => '/',
}));

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('<HeaderAuth />', () => {
  it('renders Sign in for anonymous users', async () => {
    render(
      <TestProviders>
        <HeaderAuth />
      </TestProviders>,
    );
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /sign in/i }),
      ).toBeInTheDocument();
    });
  });

  it('renders the user avatar when /auth/me succeeds', async () => {
    window.localStorage.setItem('user_token', 'jwt-1');
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
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
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          },
        );
      }
      if (url.endsWith('/api/v1/favorites')) {
        return new Response(
          JSON.stringify({ items: [], total: 0 }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          },
        );
      }
      return new Response('', { status: 404 });
    });
    render(
      <TestProviders>
        <HeaderAuth />
      </TestProviders>,
    );
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: 'me@x.com' }),
      ).toBeInTheDocument();
    });
  });
});
