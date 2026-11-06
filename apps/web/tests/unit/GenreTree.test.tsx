import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { GenreTree, subgenreSummary } from '@/components/genres/GenreTree';
import type { Genre } from '@/lib/types';

// next-intl's Link needs the app router/provider; a plain anchor is enough here.
vi.mock('@/i18n/navigation', () => ({
  Link: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

const g = (over: Partial<Genre> & Pick<Genre, 'id' | 'slug' | 'name'>): Genre => ({
  color_hex: '#8B4EE8',
  parent_id: null,
  station_count: 100,
  children: [],
  ...over,
});

const child = (id: number, slug: string, name: string, count: number): Genre =>
  g({ id, slug, name, parent_id: 1, station_count: count });

const house = g({
  id: 1,
  slug: 'house',
  name: 'House',
  station_count: 554,
  children: [
    child(3, 'deep-house', 'Deep House', 163),
    child(4, 'tech-house', 'Tech House', 50),
    child(5, 'afro-house', 'Afro House', 20),
    child(6, 'nu-disco', 'Nu Disco', 0),
  ],
});

const genres: Genre[] = [
  g({ id: 2, slug: 'techno', name: 'Techno', station_count: 232 }),
  house,
  g({ id: 7, slug: 'electronic', name: 'Electronic', station_count: 651 }),
  g({ id: 8, slug: 'makina', name: 'Makina', station_count: 4 }),
  g({ id: 9, slug: 'schranz', name: 'Schranz', station_count: 0 }),
];

const renderTree = () =>
  render(<GenreTree genres={genres} countLabel={(n) => `${n} estaciones`} moreLabel="Más géneros" />);

describe('subgenreSummary', () => {
  it('names the first two subgenres with stations and counts the rest', () => {
    expect(subgenreSummary(house)).toBe('Deep House · Tech House · +1');
  });
  it('is empty without subgenres, and ignores empty ones', () => {
    expect(subgenreSummary(genres[0]!)).toBe('');
    expect(subgenreSummary({ ...house, children: [child(6, 'x', 'X', 0)] })).toBe('');
  });
  it('does not add "+N" when everything fits', () => {
    expect(subgenreSummary({ ...house, children: [child(3, 'd', 'Deep House', 5)] })).toBe(
      'Deep House',
    );
  });
});

describe('<GenreTree />', () => {
  it('orders main genres by number of stations, biggest first', () => {
    renderTree();
    const grid = screen.getAllByRole('link', { name: /estaciones/ });
    expect(grid.map((a) => a.getAttribute('href'))).toEqual([
      '/genres/electronic',
      '/genres/house',
      '/genres/techno',
    ]);
  });

  it('moves small genres to the "Más géneros" pills and hides empty ones', () => {
    renderTree();
    const more = screen.getByRole('navigation', { name: 'Más géneros' });
    expect(within(more).getByRole('link', { name: /Makina · 4/ })).toHaveAttribute(
      'href',
      '/genres/makina',
    );
    expect(screen.queryByText(/Schranz/)).toBeNull();
  });

  it('shows the subgenre summary as plain text inside the card, never as nested links', () => {
    const { container } = renderTree();
    expect(screen.getByText('Deep House · Tech House · +1')).toBeInTheDocument();
    expect(container.querySelectorAll('a a')).toHaveLength(0);
    expect(screen.queryByRole('link', { name: 'Deep House' })).toBeNull();
  });

  it('renders no "Más géneros" block when every genre is big', () => {
    render(
      <GenreTree genres={[genres[0]!]} countLabel={(n) => `${n} estaciones`} moreLabel="Más géneros" />,
    );
    expect(screen.queryByRole('navigation', { name: 'Más géneros' })).toBeNull();
  });
});
