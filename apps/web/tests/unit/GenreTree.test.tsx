import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { GenreTree } from '@/components/genres/GenreTree';
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
  station_count: 10,
  children: [],
  ...over,
});

const genres: Genre[] = [
  g({
    id: 1,
    slug: 'house',
    name: 'House',
    children: [
      g({ id: 3, slug: 'deep-house', name: 'Deep House', parent_id: 1, station_count: 5 }),
      g({ id: 4, slug: 'afro-house', name: 'Afro House', parent_id: 1, station_count: 0 }),
    ],
  }),
  g({ id: 2, slug: 'techno', name: 'Techno' }),
];

const renderTree = () =>
  render(<GenreTree genres={genres} countLabel={(n) => `${n} estaciones`} />);

describe('<GenreTree />', () => {
  it('links every root genre', () => {
    renderTree();
    expect(screen.getByRole('link', { name: /^House/ })).toHaveAttribute('href', '/genres/house');
    expect(screen.getByRole('link', { name: /^Techno/ })).toHaveAttribute('href', '/genres/techno');
  });

  it('shows subgenres that have stations as links, and hides empty ones', () => {
    renderTree();
    expect(screen.getByRole('link', { name: 'Deep House' })).toHaveAttribute(
      'href',
      '/genres/deep-house',
    );
    expect(screen.queryByRole('link', { name: 'Afro House' })).toBeNull();
  });

  it('never nests a link inside another link', () => {
    const { container } = renderTree();
    expect(container.querySelectorAll('a a')).toHaveLength(0);
    const card = screen.getByRole('link', { name: /^House/ }).closest('div.group') as HTMLElement;
    expect(within(card).getAllByRole('link')).toHaveLength(2);
  });

  it('roots without subgenres render no list', () => {
    renderTree();
    const card = screen.getByRole('link', { name: /^Techno/ }).closest('div.group') as HTMLElement;
    expect(within(card).queryByRole('list')).toBeNull();
  });
});
