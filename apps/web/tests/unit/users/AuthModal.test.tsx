import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AuthModal } from '@/components/auth/AuthModal';
import { TestProviders } from './test-utils';

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
}));

describe('<AuthModal />', () => {
  it('renders sign in by default and switches tabs', () => {
    render(
      <TestProviders>
        <AuthModal onClose={() => {}} />
      </TestProviders>,
    );
    expect(
      screen.getAllByRole('button', { name: /sign in/i })[0],
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole('button', { name: /^sign up$/i }),
    );
    // After switching, confirm-password input appears
    expect(
      screen.getByLabelText(/confirm password/i),
    ).toBeInTheDocument();
  });

  it('shows the prompt headline when provided', () => {
    render(
      <TestProviders>
        <AuthModal onClose={() => {}} prompt="Sign in to vote" />
      </TestProviders>,
    );
    expect(screen.getByText(/Sign in to vote/i)).toBeInTheDocument();
  });

  it('surfaces invalid_credentials as a friendly error', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('', { status: 401 }),
    );
    render(
      <TestProviders>
        <AuthModal onClose={() => {}} />
      </TestProviders>,
    );
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'a@b.com' },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: 'pw1234567' },
    });
    const submitButtons = screen.getAllByRole('button', { name: /sign in/i });
    const submitBtn = submitButtons[submitButtons.length - 1]!;
    fireEvent.submit(submitBtn.closest('form')!);
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        /Wrong email or password/i,
      );
    });
  });
});
