import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { UpcomingFestivals } from '@/components/festivals/UpcomingFestivals';
import type { Festival } from '@/lib/festivals';

// next-intl's Link needs the app router/provider; a plain anchor with the locale prefix is enough here.
vi.mock('@/i18n/navigation', () => ({
  Link: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={`/en${href}`} {...rest}>
      {children}
    </a>
  ),
}));

const labels = { title: 'Upcoming Techno festivals', viewAll: 'Full calendar', source: 'Festival data from gofestivals' };

const festivals: Festival[] = [
  { id: '165', name: "Astropolis L'Hiver", startDate: '2026-12-05T00:00:00.000Z', endDate: '2026-12-09T00:00:00.000Z', location: 'Brest, France', locationEn: null, countryCode: null, website: null, imageUrl: null, description: null, descriptionEn: null, genres: [] },
  { id: '51', name: 'Listen Festival', startDate: '2026-11-21T00:00:00.000Z', endDate: null, location: null, locationEn: null, countryCode: null, website: null, imageUrl: null, description: null, descriptionEn: null, genres: [] },
];

describe('UpcomingFestivals', () => {
  it('renders nothing when there are no festivals', () => {
    const { container } = render(<UpcomingFestivals festivals={[]} locale="en" labels={labels} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('links each card to its festival page on the radio and the heading link to the index', () => {
    render(<UpcomingFestivals festivals={festivals} locale="en" labels={labels} />);
    expect(screen.getByRole('heading', { name: labels.title })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Astropolis/ })).toHaveAttribute(
      'href',
      '/en/festivals/165/astropolis-l-hiver',
    );
    expect(screen.getByRole('link', { name: labels.viewAll })).toHaveAttribute('href', '/en/festivals');
  });

  it('skips an empty location and still shows the localized one', () => {
    render(<UpcomingFestivals festivals={festivals} locale="es" labels={labels} />);
    expect(screen.getByRole('link', { name: /Listen Festival/ })).toHaveAttribute(
      'href',
      '/en/festivals/51/listen-festival',
    );
    expect(screen.getByText('Brest, France')).toBeInTheDocument();
  });

  it('does not add nofollow (internal links)', () => {
    render(<UpcomingFestivals festivals={festivals} locale="en" labels={labels} />);
    for (const a of screen.getAllByRole('link')) {
      expect(a.getAttribute('rel') ?? '').not.toContain('nofollow');
    }
  });
});
