'use client';

import { useEffect, useRef, useState } from 'react';
import { Search } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { Link, useRouter } from '@/i18n/navigation';
import { useStationSuggestions } from '@/hooks/useStationSuggestions';
import { cn } from '@/lib/utils';

interface SearchBoxProps {
  variant?: 'header' | 'drawer';
  onNavigate?: () => void;
}

export function SearchBox({ variant = 'header', onNavigate }: SearchBoxProps) {
  const t = useTranslations('search');
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement | null>(null);

  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const { suggestions, loading } = useStationSuggestions(query);

  const trimmed = query.trim();
  const showList = open && trimmed.length >= 2;

  // Firma estable: una respuesta tardía con el mismo contenido (nueva
  // identidad de array) no debe perder la selección de teclado.
  const suggestionsKey = suggestions.map((s) => s.slug).join('|');
  useEffect(() => {
    setActiveIndex(-1);
  }, [suggestionsKey]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: PointerEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', handler);
    return () => document.removeEventListener('pointerdown', handler);
  }, [open]);

  const navigate = (href: string) => {
    setOpen(false);
    setQuery('');
    onNavigate?.();
    router.push(href);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      if (showList) {
        // En el drawer, el primer Esc cierra solo el dropdown, no el menú.
        e.stopPropagation();
        setOpen(false);
      } else if (query) {
        e.stopPropagation();
        setQuery('');
      }
      return;
    }
    if (!showList) return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (suggestions.length === 0) return;
      const delta = e.key === 'ArrowDown' ? 1 : -1;
      setActiveIndex(
        (prev) => (prev + delta + suggestions.length) % suggestions.length,
      );
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      const active = suggestions[activeIndex];
      if (active) {
        navigate(`/stations/${active.slug}`);
      } else if (trimmed.length >= 2) {
        navigate(`/search?q=${encodeURIComponent(trimmed)}`);
      }
    }
  };

  return (
    <div ref={containerRef} className="relative">
      <label
        className={cn(
          'flex items-center gap-2 rounded-xl border border-fg-3 bg-bg-2 px-3 py-1.5 focus-within:border-fg-2',
          variant === 'drawer' && 'px-3 py-2',
        )}
      >
        <Search size={16} aria-hidden className="shrink-0 text-fg-2" />
        <input
          type="search"
          role="combobox"
          aria-label={t('ariaLabel')}
          aria-expanded={showList}
          aria-controls="station-search-listbox"
          aria-activedescendant={
            activeIndex >= 0 ? `station-search-opt-${activeIndex}` : undefined
          }
          aria-autocomplete="list"
          enterKeyHint="search"
          value={query}
          placeholder={t('placeholder')}
          maxLength={100}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          className={cn(
            'bg-transparent text-sm text-fg-0 outline-none placeholder:text-fg-2',
            variant === 'header'
              ? 'w-32 transition-[width] duration-200 focus:w-52'
              : 'w-full',
          )}
        />
      </label>

      {showList ? (
        <ul
          role="listbox"
          id="station-search-listbox"
          className="absolute top-full z-50 mt-2 max-h-96 w-full min-w-64 overflow-y-auto rounded-xl border border-fg-3/40 bg-bg-2 py-1 shadow-sticker-lg"
        >
          {suggestions.map((s, i) => (
            <li
              key={s.slug}
              role="option"
              id={`station-search-opt-${i}`}
              aria-selected={i === activeIndex}
            >
              <Link
                href={`/stations/${s.slug}`}
                onClick={(e) => {
                  e.preventDefault();
                  navigate(`/stations/${s.slug}`);
                }}
                onPointerMove={() => setActiveIndex(i)}
                className={cn(
                  'flex items-baseline justify-between gap-2 px-3 py-2 text-sm transition-colors',
                  i === activeIndex ? 'bg-bg-3 text-fg-0' : 'text-fg-1',
                )}
              >
                <span className="truncate">{s.name}</span>
                {s.country_code ? (
                  <span className="shrink-0 font-mono text-[10px] uppercase tracking-widest text-fg-2">
                    {s.country_code}
                  </span>
                ) : null}
              </Link>
            </li>
          ))}
          {!loading && suggestions.length === 0 ? (
            <li className="px-3 py-2 text-sm text-fg-2">{t('noSuggestions')}</li>
          ) : null}
          {suggestions.length > 0 ? (
            <li className="border-t border-fg-3/30">
              <Link
                href={`/search?q=${encodeURIComponent(trimmed)}`}
                onClick={(e) => {
                  e.preventDefault();
                  navigate(`/search?q=${encodeURIComponent(trimmed)}`);
                }}
                className="block px-3 py-2 font-mono text-[11px] uppercase tracking-widest text-fg-2 transition-colors hover:text-fg-0"
              >
                {t('viewAll', { query: trimmed })}
              </Link>
            </li>
          ) : null}
        </ul>
      ) : null}
    </div>
  );
}
