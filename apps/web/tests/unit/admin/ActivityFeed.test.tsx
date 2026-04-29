import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  ActivityFeed,
  formatRelative,
} from '@/components/admin/ActivityFeed';
import type { ActivityEntry } from '@/lib/admin/dashboard';

const mk = (overrides: Partial<ActivityEntry> = {}): ActivityEntry => ({
  id: 1,
  decision: 'approve',
  station_id: 'b6c0e3a4-0000-0000-0000-000000000001',
  station_name: 'Yammat FM',
  station_slug: 'yammat-fm',
  admin_email: 'me@x.com',
  notes: null,
  created_at: new Date().toISOString(),
  ...overrides,
});

describe('formatRelative', () => {
  const now = new Date('2026-04-29T12:00:00Z');

  it('returns "just now" for under 60s', () => {
    expect(
      formatRelative('2026-04-29T11:59:30Z', now),
    ).toBe('just now');
  });

  it('returns minutes for <60min', () => {
    expect(formatRelative('2026-04-29T11:55:00Z', now)).toBe('5m ago');
  });

  it('returns hours for <24h', () => {
    expect(formatRelative('2026-04-29T10:00:00Z', now)).toBe('2h ago');
  });

  it('returns days for <7d', () => {
    expect(formatRelative('2026-04-27T12:00:00Z', now)).toBe('2d ago');
  });

  it('returns date for >=7d', () => {
    const result = formatRelative('2026-04-01T12:00:00Z', now);
    expect(result).not.toBe('28d ago');
  });
});

describe('<ActivityFeed />', () => {
  it('shows empty state', () => {
    render(<ActivityFeed entries={[]} />);
    expect(screen.getByText(/No activity yet/i)).toBeInTheDocument();
  });

  it('renders one row per entry', () => {
    render(
      <ActivityFeed
        entries={[mk({ id: 1 }), mk({ id: 2, decision: 'reject' })]}
      />,
    );
    const list = screen.getByTestId('activity-feed');
    expect(list.children).toHaveLength(2);
  });

  it('links entries to /admin/stations/{id} when slug is present', () => {
    render(<ActivityFeed entries={[mk()]} />);
    const link = screen.getByRole('link', { name: /Yammat FM/i });
    expect(link).toHaveAttribute(
      'href',
      '/admin/stations/b6c0e3a4-0000-0000-0000-000000000001',
    );
  });

  it('shows "(deleted station)" when slug is null', () => {
    render(
      <ActivityFeed
        entries={[mk({ station_slug: null, station_name: null })]}
      />,
    );
    expect(screen.getByText(/deleted station/i)).toBeInTheDocument();
  });

  it('shows decision badge text', () => {
    render(<ActivityFeed entries={[mk({ decision: 'toggle_curated' })]} />);
    expect(screen.getByText('toggle_curated')).toBeInTheDocument();
  });
});
