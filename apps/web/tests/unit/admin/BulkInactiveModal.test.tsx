import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { BulkInactiveModal } from '@/components/admin/BulkInactiveModal';
import { storeToken } from '@/lib/admin/api';

beforeEach(() => storeToken('jwt-1'));

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

const NAMES = [
  'Alpha',
  'Beta',
  'Gamma',
  'Delta',
  'Epsilon',
  'Zeta',
  'Eta',
  'Theta',
  'Iota',
  'Kappa',
  'Lambda',
  'Mu',
];

describe('<BulkInactiveModal />', () => {
  it('renders count and shows up to 10 names + "N más"', () => {
    render(
      <BulkInactiveModal
        selectedIds={NAMES.map((_, i) => `id-${i}`)}
        selectedNames={NAMES}
        onClose={() => {}}
        onCompleted={() => {}}
      />,
    );
    // "12 stations"
    expect(screen.getByText(/12 stations/)).toBeInTheDocument();
    // 10 names visible
    expect(screen.getByText(/· Alpha/)).toBeInTheDocument();
    expect(screen.getByText(/· Kappa/)).toBeInTheDocument();
    // 11th not visible
    expect(screen.queryByText(/· Lambda/)).not.toBeInTheDocument();
    // overflow message
    expect(screen.getByText(/y 2 más/i)).toBeInTheDocument();
  });

  it('submits with the bulk endpoint and reason', async () => {
    const onCompleted = vi.fn();
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          affected: 2,
          skipped: 0,
          station_ids_affected: ['id-0', 'id-1'],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    render(
      <BulkInactiveModal
        selectedIds={['id-0', 'id-1']}
        selectedNames={['A', 'B']}
        onClose={() => {}}
        onCompleted={onCompleted}
      />,
    );
    fireEvent.change(screen.getByLabelText(/Reason/i), {
      target: { value: 'cleanup test' },
    });
    fireEvent.click(
      screen.getByRole('button', { name: /Mark 2 as inactive/i }),
    );
    await waitFor(() => {
      expect(onCompleted).toHaveBeenCalledWith(2, 0);
    });
    const fetchSpy = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    const init = fetchSpy.mock.calls[0]![1] as RequestInit;
    const body = JSON.parse(String(init.body));
    expect(body).toEqual({
      station_ids: ['id-0', 'id-1'],
      new_status: 'inactive',
      reason: 'cleanup test',
    });
  });
});
