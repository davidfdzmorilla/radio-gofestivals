'use client';

import { useEffect, useRef, useState } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { Search } from 'lucide-react';
import { listStations } from '@/lib/api';
import { SITE_URL } from '@/lib/site';
import type { StationSummary } from '@/lib/types';

function buildSnippet(slug: string, locale: string, alt: string): string {
  const stationUrl = `${SITE_URL}/${locale}/stations/${slug}`;
  const badgeUrl = `${SITE_URL}/badges/listen-${locale === 'es' ? 'es' : 'en'}.svg`;
  return [
    `<a href="${stationUrl}" title="${alt}">`,
    `  <img src="${badgeUrl}" alt="${alt}" width="200" height="56" loading="lazy" />`,
    `</a>`,
  ].join('\n');
}

export function BadgeSnippetGenerator() {
  const t = useTranslations('forStations');
  const locale = useLocale();

  const [query, setQuery] = useState('');
  const [results, setResults] = useState<StationSummary[]>([]);
  const [selected, setSelected] = useState<StationSummary | null>(null);
  const [copied, setCopied] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) return;
    debounceRef.current = setTimeout(() => {
      listStations({ q, size: 6 })
        .then((page) => setResults(page.items))
        .catch(() => setResults([]));
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  const snippet = selected
    ? buildSnippet(selected.slug, locale, t('badgeAlt'))
    : null;

  const copySnippet = async () => {
    if (!snippet) return;
    try {
      await navigator.clipboard.writeText(snippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard bloqueado (permisos): el textarea sigue siendo copiable a mano.
    }
  };

  return (
    <div className="space-y-4">
      <label className="flex items-center gap-3 rounded-xl border border-fg-3 bg-bg-2 px-4 py-3 focus-within:border-fg-2">
        <Search size={18} aria-hidden className="shrink-0 text-fg-2" />
        <input
          type="search"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setSelected(null);
            if (e.target.value.trim().length < 2) setResults([]);
          }}
          placeholder={t('searchPlaceholder')}
          maxLength={100}
          className="w-full bg-transparent text-fg-0 outline-none placeholder:text-fg-2"
        />
      </label>

      {!selected && results.length > 0 && (
        <ul className="overflow-hidden rounded-xl border border-fg-3 divide-y divide-fg-3/50">
          {results.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => setSelected(s)}
                className="flex w-full items-baseline justify-between gap-4 bg-bg-2 px-4 py-2.5 text-left transition-colors hover:bg-bg-3"
              >
                <span className="truncate font-medium text-fg-0">{s.name}</span>
                <span className="shrink-0 font-mono text-[11px] uppercase text-fg-2">
                  {s.country_code ?? ''}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {selected && snippet && (
        <div className="space-y-3">
          {/* Vista previa del badge real que verá su web */}
          <a
            href={`/${locale}/stations/${selected.slug}`}
            className="inline-block"
          >
            {/* eslint-disable-next-line @next/next/no-img-element -- SVG estático, mismo asset que usará el embed externo */}
            <img
              src={`/badges/listen-${locale === 'es' ? 'es' : 'en'}.svg`}
              alt={t('badgeAlt')}
              width={200}
              height={56}
            />
          </a>
          <div>
            <p className="mb-1.5 font-mono text-[11px] font-semibold uppercase tracking-widest text-fg-2">
              {t('snippetLabel')} — {selected.name}
            </p>
            <textarea
              readOnly
              value={snippet}
              rows={3}
              onFocus={(e) => e.currentTarget.select()}
              className="w-full rounded-xl border border-fg-3 bg-bg-0 p-3 font-mono text-xs text-fg-1 outline-none focus:border-fg-2"
            />
          </div>
          <button
            type="button"
            onClick={copySnippet}
            className="inline-flex items-center rounded-md bg-wave px-4 py-2 font-display text-sm font-medium text-fg-0 shadow-sticker transition-all hover:bg-magenta hover:shadow-sticker-magenta"
          >
            {copied ? t('copied') : t('copy')}
          </button>
        </div>
      )}
    </div>
  );
}
