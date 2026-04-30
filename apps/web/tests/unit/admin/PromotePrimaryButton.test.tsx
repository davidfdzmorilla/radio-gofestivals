import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { PromotePrimaryButton } from '@/components/admin/PromotePrimaryButton';
import { storeToken } from '@/lib/admin/api';

beforeEach(() => storeToken('jwt-1'));

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe('<PromotePrimaryButton />', () => {
  it('starts with the default label', () => {
    render(
      <PromotePrimaryButton streamId="abc" onPromoted={() => {}} />,
    );
    expect(screen.getByRole('button')).toHaveTextContent(
      /Promote to primary/i,
    );
  });

  it('first click switches to confirm state', () => {
    render(
      <PromotePrimaryButton streamId="abc" onPromoted={() => {}} />,
    );
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByRole('button')).toHaveTextContent(/confirm/i);
    expect(screen.getByRole('button')).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('second click fires the promote API and onPromoted callback', async () => {
    const onPromoted = vi.fn();
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          promoted_stream_id: 'abc',
          demoted_stream_id: null,
          station_id: 'sid',
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        },
      ),
    );
    render(
      <PromotePrimaryButton streamId="abc" onPromoted={onPromoted} />,
    );
    fireEvent.click(screen.getByRole('button'));
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() => {
      expect(onPromoted).toHaveBeenCalledTimes(1);
    });
    const fetchSpy = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    expect(String(fetchSpy.mock.calls[0]![0])).toContain(
      '/admin/streams/abc/promote-primary',
    );
  });

  it('shows "Ya es primary" when already_primary', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'already_primary' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    render(
      <PromotePrimaryButton streamId="abc" onPromoted={() => {}} />,
    );
    fireEvent.click(screen.getByRole('button'));
    fireEvent.click(screen.getByRole('button'));
    await waitFor(() => {
      expect(screen.getByText(/Ya es primary/i)).toBeInTheDocument();
    });
  });
});
