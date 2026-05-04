import { notFound } from 'next/navigation';
import type { Metadata } from 'next';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Link } from '@/i18n/navigation';
import { getGenresTree, listStations } from '@/lib/api';
import { StationGrid } from '@/components/stations/StationGrid';
import { SidebarFilters } from '@/components/layout/SidebarFilters';
import { PublicPagination } from '@/components/PublicPagination';
import type { Genre } from '@/lib/types';

export const revalidate = 300;

export async function generateStaticParams() {
  try {
    const genres = await getGenresTree();
    return genres
      .filter((g) => g.parent_id === null)
      .map((g) => ({ slug: g.slug }));
  } catch {
    return [];
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}): Promise<Metadata> {
  const { locale, slug } = await params;
  const t = await getTranslations({ locale, namespace: 'genres' });
  try {
    const genres = await getGenresTree();
    const genre = genres.find((g) => g.slug === slug);
    if (!genre) return {};
    return {
      title: t('exploreTitle', { name: genre.name }),
    };
  } catch {
    return {};
  }
}

function indexBySlug(genres: Genre[]): Record<string, Genre> {
  const out: Record<string, Genre> = {};
  const walk = (g: Genre) => {
    out[g.slug] = g;
    g.children.forEach(walk);
  };
  genres.forEach(walk);
  return out;
}

export default async function GenrePage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string; slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { locale, slug } = await params;
  const sp = await searchParams;
  setRequestLocale(locale);

  const genres = await getGenresTree();
  const genresBySlug = indexBySlug(genres);
  const genre = genresBySlug[slug];
  if (!genre) notFound();

  const country = typeof sp.country === 'string' ? sp.country : undefined;
  const curatedParam = typeof sp.curated === 'string' ? sp.curated : undefined;
  const page = typeof sp.page === 'string' ? parseInt(sp.page, 10) : 1;

  const tGenres = await getTranslations('genres');
  const tCommon = await getTranslations('common');
  const tStation = await getTranslations('station');
  const tHome = await getTranslations('home');
  const tNav = await getTranslations('nav');
  const tPagination = await getTranslations('pagination');

  const stationsPage = await listStations({
    genre: genre.slug,
    country,
    curated: curatedParam === 'true' ? true : undefined,
    page: Number.isFinite(page) && page > 0 ? page : 1,
    size: 20,
    revalidate: 300,
  });

  const countries = ['ES', 'FR', 'DE', 'IT', 'UK', 'US', 'NL', 'BE'];

  const buildPageHref = (targetPage: number): string => {
    const params = new URLSearchParams();
    if (country) params.set('country', country);
    if (curatedParam) params.set('curated', curatedParam);
    if (targetPage > 1) params.set('page', String(targetPage));
    const qs = params.toString();
    return `/${locale}/genres/${slug}${qs ? `?${qs}` : ''}`;
  };

  return (
    <div className="space-y-8">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-fg-2">
        <Link href="/" className="transition-colors hover:text-fg-0">
          {tNav('home')}
        </Link>
        <span>/</span>
        <span className="text-fg-1">{tGenres('title')}</span>
      </nav>

      {/* Hero con overlay sólido para A11y */}
      <header className="relative overflow-hidden rounded-2xl border border-fg-3">
        <div
          aria-hidden
          className="absolute inset-0"
          style={{ backgroundColor: genre.color_hex, opacity: 0.25 }}
        />
        <div
          aria-hidden
          className="absolute inset-0 bg-gradient-to-br from-bg-0/80 via-bg-0/70 to-bg-0/85"
        />
        <div className="relative px-6 py-10 sm:px-10">
          <p className="font-mono text-[11px] uppercase tracking-widest text-fg-2">
            {tGenres('title')}
          </p>
          <h1 className="mt-2 font-display text-[clamp(2.25rem,5vw,3.75rem)] font-semibold leading-tight text-fg-0">
            {tGenres('exploreTitle', { name: genre.name })}
          </h1>
          <p className="mt-3 inline-flex items-center gap-2 font-mono text-xs uppercase tracking-wide text-fg-1">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ backgroundColor: genre.color_hex }}
            />
            {tGenres('stationCount', { count: stationsPage.total })}
          </p>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-[240px_1fr]">
        <SidebarFilters
          current={{ country, curated: curatedParam === 'true' }}
          countries={countries}
        />
        <div className="space-y-4">
          <StationGrid
            stations={stationsPage.items}
            genresBySlug={genresBySlug}
            maxCols={2}
            labels={{
              curated: tCommon('curated'),
              location: ({ city, country: c }) =>
                tStation('location', { city, country: c }),
              empty: tHome('featuredEmpty'),
            }}
          />
          <PublicPagination
            currentPage={stationsPage.page}
            totalPages={stationsPage.pages}
            buildHref={buildPageHref}
            pageLabel={tPagination('pageOf', {
              current: stationsPage.page,
              total: stationsPage.pages,
            })}
            prevLabel={tPagination('previous')}
            nextLabel={tPagination('next')}
          />
        </div>
      </div>
    </div>
  );
}
