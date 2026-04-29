import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { GenreSelector } from '@/components/admin/GenreSelector';
import type { FlatGenre } from '@/lib/admin/genres';

const make = (
  id: number,
  slug: string,
  name: string,
  depth = 0,
): FlatGenre => ({
  id,
  slug,
  name,
  color_hex: '#000',
  parent_id: depth === 0 ? null : 1,
  station_count: 0,
  depth,
});

const SAMPLE: FlatGenre[] = [
  make(1, 'techno', 'Techno'),
  make(13, 'minimal', 'Minimal Techno', 1),
  make(2, 'house', 'House'),
  make(11, 'tech-house', 'Tech House', 1),
];

describe('<GenreSelector />', () => {
  it('renders one checkbox per genre', () => {
    render(
      <GenreSelector
        genres={SAMPLE}
        selectedIds={[]}
        onChange={() => {}}
      />,
    );
    expect(screen.getAllByRole('checkbox')).toHaveLength(4);
  });

  it('marks selected ids as checked', () => {
    render(
      <GenreSelector
        genres={SAMPLE}
        selectedIds={[2, 13]}
        onChange={() => {}}
      />,
    );
    const checkboxes = screen.getAllByRole('checkbox') as HTMLInputElement[];
    const checkedSlugs = checkboxes
      .filter((c) => c.checked)
      .map((c) => (c.parentElement?.textContent ?? '').trim());
    expect(checkedSlugs.length).toBe(2);
  });

  it('toggle adds an id when not selected', () => {
    const spy = vi.fn();
    render(
      <GenreSelector
        genres={SAMPLE}
        selectedIds={[1]}
        onChange={spy}
      />,
    );
    const houseCheckbox = screen.getAllByRole('checkbox')[2]!;
    fireEvent.click(houseCheckbox);
    expect(spy).toHaveBeenCalledWith([1, 2]);
  });

  it('toggle removes an id when already selected', () => {
    const spy = vi.fn();
    render(
      <GenreSelector
        genres={SAMPLE}
        selectedIds={[1, 2]}
        onChange={spy}
      />,
    );
    const technoCheckbox = screen.getAllByRole('checkbox')[0]!;
    fireEvent.click(technoCheckbox);
    expect(spy).toHaveBeenCalledWith([2]);
  });

  it('search filter narrows the list (case-insensitive)', () => {
    render(
      <GenreSelector
        genres={SAMPLE}
        selectedIds={[]}
        onChange={() => {}}
      />,
    );
    fireEvent.change(screen.getByPlaceholderText(/Filtrar géneros/i), {
      target: { value: 'tech' },
    });
    // techno + minimal techno + tech-house
    expect(screen.getAllByRole('checkbox')).toHaveLength(3);
  });

  it('search filter shows no matches message when empty', () => {
    render(
      <GenreSelector
        genres={SAMPLE}
        selectedIds={[]}
        onChange={() => {}}
      />,
    );
    fireEvent.change(screen.getByPlaceholderText(/Filtrar géneros/i), {
      target: { value: 'zzzzz' },
    });
    expect(screen.queryAllByRole('checkbox')).toHaveLength(0);
    expect(screen.getByText('No matches')).toBeInTheDocument();
  });

  it('disabled prevents toggling', () => {
    const spy = vi.fn();
    render(
      <GenreSelector
        genres={SAMPLE}
        selectedIds={[]}
        onChange={spy}
        disabled
      />,
    );
    fireEvent.click(screen.getAllByRole('checkbox')[0]!);
    expect(spy).not.toHaveBeenCalled();
  });

  it('shows selected count', () => {
    render(
      <GenreSelector
        genres={SAMPLE}
        selectedIds={[1, 2]}
        onChange={() => {}}
      />,
    );
    expect(screen.getByText(/2 de 4 seleccionados/i)).toBeInTheDocument();
  });
});
