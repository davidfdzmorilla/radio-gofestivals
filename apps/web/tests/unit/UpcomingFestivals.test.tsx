import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { UpcomingFestivals } from '@/components/festivals/UpcomingFestivals';
import type { Festival } from '@/lib/festivals';

const labels = { title: 'Upcoming Techno festivals', viewAll: 'Full calendar', source: 'Festival data from gofestivals' };

const festivals: Festival[] = [
  { id: '165', name: "Astropolis L'Hiver", startDate: '2026-12-05T00:00:00.000Z', endDate: '2026-12-09T00:00:00.000Z', location: 'Brest, France' },
  { id: '51', name: 'Listen Festival', startDate: '2026-11-21T00:00:00.000Z', endDate: null, location: null },
];

describe('UpcomingFestivals', () => {
  it('renders nothing when there are no festivals', () => {
    const { container } = render(<UpcomingFestivals festivals={[]} locale="en" labels={labels} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('links each card to its gofestivals page and the heading to the calendar', () => {
    render(<UpcomingFestivals festivals={festivals} locale="en" labels={labels} />);
    expect(screen.getByRole('heading', { name: labels.title })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Astropolis/ })).toHaveAttribute(
      'href',
      'https://gofestivals.eu/en/festival/165/astropolis-l-hiver',
    );
    expect(screen.getByRole('link', { name: labels.viewAll })).toHaveAttribute(
      'href',
      'https://gofestivals.eu/en/calendar',
    );
  });

  it('uses the Spanish site and skips an empty location', () => {
    render(<UpcomingFestivals festivals={festivals} locale="es" labels={labels} />);
    expect(screen.getByRole('link', { name: /Listen Festival/ })).toHaveAttribute(
      'href',
      'https://gofestivals.es/es/festival/51/listen-festival',
    );
    expect(screen.getByText('Brest, France')).toBeInTheDocument();
  });

  it('does not add nofollow (same-owner contextual link)', () => {
    render(<UpcomingFestivals festivals={festivals} locale="en" labels={labels} />);
    for (const a of screen.getAllByRole('link')) {
      expect(a.getAttribute('rel') ?? '').not.toContain('nofollow');
    }
  });
});
