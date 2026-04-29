import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AutoCurateModal } from '@/components/admin/AutoCurateModal';
import { storeToken } from '@/lib/admin/api';

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe('<AutoCurateModal />', () => {
  it('renders with dry_run checked by default and read-only email', () => {
    render(
      <AutoCurateModal
        adminEmail="me@x.com"
        onClose={() => {}}
        onJobCreated={() => {}}
      />,
    );
    const emailInput = screen.getByDisplayValue('me@x.com') as HTMLInputElement;
    expect(emailInput).toHaveAttribute('readonly');

    const dryRun = screen.getByRole('checkbox') as HTMLInputElement;
    expect(dryRun.checked).toBe(true);
  });

  it('submits with the form values', async () => {
    storeToken('jwt-1');
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          id: 5,
          command: 'auto_curate',
          status: 'pending',
          params_json: {},
          result_json: null,
          stderr_tail: null,
          started_at: null,
          finished_at: null,
          admin_id: 'x',
          admin_email: 'me@x.com',
          created_at: '2026-04-29T00:00:00Z',
        }),
        {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        },
      ),
    );
    const onJobCreated = vi.fn();
    render(
      <AutoCurateModal
        adminEmail="me@x.com"
        onClose={() => {}}
        onJobCreated={onJobCreated}
      />,
    );

    fireEvent.change(screen.getByLabelText(/Min quality/), {
      target: { value: '80' },
    });
    fireEvent.change(screen.getByLabelText(/Limit/), {
      target: { value: '20' },
    });
    fireEvent.change(screen.getByLabelText(/Country/), {
      target: { value: 'es' },
    });
    fireEvent.click(screen.getByRole('button', { name: /run auto-curate/i }));

    await waitFor(() => {
      expect(onJobCreated).toHaveBeenCalledTimes(1);
    });

    const init = fetchSpy.mock.calls[0]![1] as RequestInit;
    const body = JSON.parse(String(init.body));
    expect(body.command).toBe('auto_curate');
    expect(body.params).toEqual({
      admin_email: 'me@x.com',
      min_quality: 80,
      limit: 20,
      country: 'ES',
      dry_run: true,
    });
  });

  it('uppercases country input as user types', () => {
    render(
      <AutoCurateModal
        adminEmail="me@x.com"
        onClose={() => {}}
        onJobCreated={() => {}}
      />,
    );
    const country = screen.getByLabelText(/Country/) as HTMLInputElement;
    fireEvent.change(country, { target: { value: 'fr' } });
    expect(country.value).toBe('FR');
  });

  it('toggles the dry-run hint when unchecked', () => {
    render(
      <AutoCurateModal
        adminEmail="me@x.com"
        onClose={() => {}}
        onJobCreated={() => {}}
      />,
    );
    expect(screen.getByText(/modo seguro/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('checkbox'));
    expect(screen.getByText(/modo real/i)).toBeInTheDocument();
  });
});
