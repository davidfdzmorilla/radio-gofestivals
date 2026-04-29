'use client';

import { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import type { FlatGenre } from '@/lib/admin/genres';
import { cn } from '@/lib/utils';

interface GenreSelectorProps {
  genres: FlatGenre[];
  selectedIds: number[];
  onChange: (ids: number[]) => void;
  disabled?: boolean;
}

export function GenreSelector({
  genres,
  selectedIds,
  onChange,
  disabled,
}: GenreSelectorProps) {
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    if (!search) return genres;
    const q = search.toLowerCase();
    return genres.filter(
      (g) =>
        g.name.toLowerCase().includes(q) ||
        g.slug.toLowerCase().includes(q),
    );
  }, [genres, search]);

  function toggle(id: number) {
    if (disabled) return;
    if (selectedIds.includes(id)) {
      onChange(selectedIds.filter((i) => i !== id));
    } else {
      onChange([...selectedIds, id]);
    }
  }

  return (
    <div className="space-y-2">
      <div className="relative">
        <Search
          size={14}
          className="text-fg-2 pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2"
        />
        <input
          type="text"
          placeholder="Filtrar géneros…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          disabled={disabled}
          className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta w-full rounded-md border px-3 py-1.5 pl-8 text-sm focus:outline-none disabled:opacity-50"
        />
      </div>

      <p className="text-fg-2 font-mono text-[10px] uppercase tracking-widest">
        {selectedIds.length} de {genres.length} seleccionados
      </p>

      <div
        className="border-fg-3/40 bg-bg-1 max-h-64 overflow-y-auto rounded-md border"
        role="listbox"
        aria-label="Genres"
        aria-multiselectable="true"
      >
        {filtered.length === 0 ? (
          <p className="text-fg-2 p-3 text-center text-sm">No matches</p>
        ) : (
          <ul className="divide-fg-3/30 divide-y">
            {filtered.map((genre) => {
              const checked = selectedIds.includes(genre.id);
              return (
                <li key={genre.id}>
                  <label
                    className={cn(
                      'hover:bg-bg-2 flex cursor-pointer items-center gap-2 px-3 py-2',
                      disabled && 'cursor-not-allowed opacity-50',
                    )}
                    style={{ paddingLeft: `${12 + genre.depth * 16}px` }}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggle(genre.id)}
                      disabled={disabled}
                      className="accent-magenta h-4 w-4"
                    />
                    <span className="text-fg-0 text-sm">{genre.name}</span>
                    <span className="text-fg-2 ml-auto font-mono text-[10px] uppercase tracking-widest">
                      {genre.slug}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
