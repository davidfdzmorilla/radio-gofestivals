import type { Metadata } from 'next';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Search } from 'lucide-react';
import { Link } from '@/i18n/navigation';
import { getGenresTree, listStations } from '@/lib/api';
import { StationGrid } from '@/components/stations/StationGrid';
import { PublicPagination } from '@/components/PublicPagination';
import { buildAlternates } from '@/lib/seo';
import type { Genre, StationsPage } from '@/lib/types';

export const revalidate = 300;

export async function generateMetadata({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}): Promise<Metadata> {
  const { locale } = await params;
  const sp = await searchParams;
  const t = await getTranslations({ locale, namespace: 'search' });
  const hasQuery = typeof sp.q === 'string' && sp.q.length > 0;
  return {
    title: t('metaTitle'),
    description: t('metaDescription'),
    alternates: buildAlternates(locale, '/search'),
    // Solo el /search limpio (target del SearchAction) es indexable; los
    // resultados parametrizados serían combinatoria infinita de thin pages.
    ...(hasQuery ? { robots: { index: false } } : {}),
  };
}

export default async function SearchPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { locale } = await params;
  const sp = await searchParams;
  setRequestLocale(locale);

  const q = typeof sp.q === 'string' ? sp.q.trim().slice(0, 100) : '';
  const pageParam = typeof sp.page === 'string' ? parseInt(sp.page, 10) : 1;
  const page = Number.isFinite(pageParam) && pageParam > 0 ? pageParam : 1;

  const t = await getTranslations('search');
  const tNav = await getTranslations('nav');
  const tCommon = await getTranslations('common');
  const tStation = await getTranslations('station');
  const tPagination = await getTranslations('pagination');

  let results: StationsPage | null = null;
  let genresTree: Genre[] = [];
  if (q.length >= 2) {
    [results, genresTree] = await Promise.all([
      listStations({ q, page, size: 20, revalidate: 60 }).catch(() => null),
      getGenresTree().catch(() => []),
    ]);
  }

  const genresBySlug: Record<string, Genre> = {};
  const walk = (list: Genre[]) => {
    for (const g of list) {
      genresBySlug[g.slug] = g;
      walk(g.children);
    }
  };
  walk(genresTree);

  const buildPageHref = (targetPage: number): string => {
    const qs = new URLSearchParams({ q });
    if (targetPage > 1) qs.set('page', String(targetPage));
    return `/${locale}/search?${qs}`;
  };

  return (
    <div className="space-y-8">
      <nav className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-fg-2">
        <Link href="/" className="transition-colors hover:text-fg-0">
          {tNav('home')}
        </Link>
        <span>/</span>
        <span className="text-fg-1">{t('title')}</span>
      </nav>

      <header>
        <h1 className="font-display text-[clamp(2.25rem,5vw,3.75rem)] font-semibold leading-tight text-fg-0">
          {t('title')}
        </h1>
      </header>

      {/* Form GET puro: funciona sin JS y mantiene la página como server
          component; el SearchAction del JSON-LD apunta a esta misma URL. */}
      <form method="get" action={`/${locale}/search`} className="max-w-xl">
        <label className="flex items-center gap-3 rounded-xl border border-fg-3 bg-bg-2 px-4 py-3 focus-within:border-fg-2">
          <Search size={18} aria-hidden className="shrink-0 text-fg-2" />
          <input
            type="search"
            name="q"
            defaultValue={q}
            placeholder={t('placeholder')}
            minLength={2}
            maxLength={100}
            className="w-full bg-transparent text-fg-0 outline-none placeholder:text-fg-2"
          />
        </label>
      </form>

      {q.length >= 2 ? (
        results && results.items.length > 0 ? (
          <section className="space-y-4">
            <h2 className="font-display text-xl font-semibold text-fg-0">
              {t('resultsFor', { query: q })}
            </h2>
            <StationGrid
              stations={results.items}
              genresBySlug={genresBySlug}
              maxCols={3}
              labels={{
                curated: tCommon('curated'),
                location: ({ city, country: c }) =>
                  tStation('location', { city, country: c }),
                empty: t('noResults', { query: q }),
              }}
            />
            <PublicPagination
              currentPage={results.page}
              totalPages={results.pages}
              buildHref={buildPageHref}
              pageLabel={tPagination('pageOf', {
                current: results.page,
                total: results.pages,
              })}
              prevLabel={tPagination('previous')}
              nextLabel={tPagination('next')}
            />
          </section>
        ) : (
          <p className="text-fg-2">{t('noResults', { query: q })}</p>
        )
      ) : (
        <p className="text-fg-2">{t('hint')}</p>
      )}
    </div>
  );
}
