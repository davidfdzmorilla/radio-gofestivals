import { notFound } from 'next/navigation';
import type { Metadata } from 'next';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Link } from '@/i18n/navigation';
import { getCountryFacets, getGenresTree, listStations } from '@/lib/api';
import { StationGrid } from '@/components/stations/StationGrid';
import { PublicPagination } from '@/components/PublicPagination';
import { JsonLd } from '@/components/seo/JsonLd';
import { SITE_URL } from '@/lib/site';
import {
  buildAlternates,
  COMBO_GATE_MIN_STATIONS,
  regionName,
} from '@/lib/seo';
import type { Genre } from '@/lib/types';

export const revalidate = 300;

function findGenre(genres: Genre[], slug: string): Genre | null {
  for (const g of genres) {
    if (g.slug === slug) return g;
    const child = findGenre(g.children, slug);
    if (child) return child;
  }
  return null;
}

/**
 * El combo solo existe si el género tiene >= COMBO_GATE_MIN_STATIONS
 * emisoras en ese país. Misma fuente (facets/countries?genre=) que el
 * sitemap y que los enlaces desde los hubs, para que nunca diverjan.
 */
async function gatedCombo(code: string, genreSlug: string) {
  const [facets, genresTree] = await Promise.all([
    getCountryFacets({ genre: genreSlug }).catch(() => []),
    getGenresTree().catch(() => []),
  ]);
  const genre = findGenre(genresTree, genreSlug);
  const facet = facets.find((f) => f.code.toLowerCase() === code.toLowerCase());
  if (!genre || !facet || facet.station_count < COMBO_GATE_MIN_STATIONS) {
    return null;
  }
  return { genre, facet, genresTree };
}

export async function generateStaticParams() {
  try {
    const genres = await getGenresTree();
    const roots = genres.filter((g) => g.parent_id === null);
    const pairs = await Promise.all(
      roots.map(async (g) => {
        const facets = await getCountryFacets({ genre: g.slug }).catch(
          () => [],
        );
        return facets
          .filter((f) => f.station_count >= COMBO_GATE_MIN_STATIONS)
          .map((f) => ({ code: f.code.toLowerCase(), genre: g.slug }));
      }),
    );
    return pairs.flat();
  } catch {
    return [];
  }
}

export async function generateMetadata({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string; code: string; genre: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}): Promise<Metadata> {
  const { locale, code, genre: genreSlug } = await params;
  const sp = await searchParams;
  const t = await getTranslations({ locale, namespace: 'countries' });
  const tPagination = await getTranslations({
    locale,
    namespace: 'pagination',
  });
  const pageParam = typeof sp.page === 'string' ? parseInt(sp.page, 10) : 1;
  const page = Number.isFinite(pageParam) && pageParam > 0 ? pageParam : 1;
  const base = `/countries/${code.toLowerCase()}/${genreSlug}`;
  const alternates = buildAlternates(
    locale,
    page > 1 ? `${base}?page=${page}` : base,
  );
  const combo = await gatedCombo(code, genreSlug);
  if (!combo) return { alternates };
  const name = regionName(locale, combo.facet.code);
  const pageSuffix = page > 1 ? tPagination('pageSuffix', { page }) : '';
  return {
    title:
      t('comboMetaTitle', {
        genre: combo.genre.name,
        name,
        count: combo.facet.station_count,
      }) + pageSuffix,
    description: t('comboMetaDescription', {
      genre: combo.genre.name,
      name,
      count: combo.facet.station_count,
    }),
    alternates,
  };
}

export default async function CountryGenrePage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string; code: string; genre: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { locale, code, genre: genreSlug } = await params;
  const sp = await searchParams;
  setRequestLocale(locale);

  const combo = await gatedCombo(code, genreSlug);
  if (!combo) notFound();
  const { genre, facet, genresTree } = combo;

  const pageParam = typeof sp.page === 'string' ? parseInt(sp.page, 10) : 1;
  const page = Number.isFinite(pageParam) && pageParam > 0 ? pageParam : 1;

  const t = await getTranslations('countries');
  const tNav = await getTranslations('nav');
  const tCommon = await getTranslations('common');
  const tStation = await getTranslations('station');
  const tPagination = await getTranslations('pagination');

  const stationsPage = await listStations({
    genre: genre.slug,
    country: facet.code,
    page,
    size: 20,
    revalidate: 300,
  });

  const genresBySlug: Record<string, Genre> = {};
  const walk = (list: Genre[]) => {
    for (const g of list) {
      genresBySlug[g.slug] = g;
      walk(g.children);
    }
  };
  walk(genresTree);

  const name = regionName(locale, facet.code);
  const codeLower = facet.code.toLowerCase();
  const basePath = `/countries/${codeLower}/${genre.slug}`;

  const buildPageHref = (targetPage: number): string =>
    `/${locale}${basePath}${targetPage > 1 ? `?page=${targetPage}` : ''}`;

  const breadcrumbLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      {
        '@type': 'ListItem',
        position: 1,
        name: tNav('home'),
        item: `${SITE_URL}/${locale}`,
      },
      {
        '@type': 'ListItem',
        position: 2,
        name: t('title'),
        item: `${SITE_URL}/${locale}/countries`,
      },
      {
        '@type': 'ListItem',
        position: 3,
        name,
        item: `${SITE_URL}/${locale}/countries/${codeLower}`,
      },
      {
        '@type': 'ListItem',
        position: 4,
        name: genre.name,
        item: `${SITE_URL}/${locale}${basePath}`,
      },
    ],
  };
  const collectionLd = {
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    name: t('comboTitle', { genre: genre.name, name }),
    url: `${SITE_URL}/${locale}${basePath}`,
    inLanguage: locale,
    mainEntity: {
      '@type': 'ItemList',
      numberOfItems: stationsPage.total,
      itemListElement: stationsPage.items.map((s, i) => ({
        '@type': 'ListItem',
        position: (page - 1) * 20 + i + 1,
        name: s.name,
        url: `${SITE_URL}/${locale}/stations/${s.slug}`,
      })),
    },
  };

  return (
    <div className="space-y-8">
      <nav className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-fg-2">
        <Link href="/" className="transition-colors hover:text-fg-0">
          {tNav('home')}
        </Link>
        <span>/</span>
        <Link href="/countries" className="transition-colors hover:text-fg-0">
          {t('title')}
        </Link>
        <span>/</span>
        <Link
          href={`/countries/${codeLower}`}
          className="transition-colors hover:text-fg-0"
        >
          {name}
        </Link>
        <span>/</span>
        <span className="text-fg-1">{genre.name}</span>
      </nav>

      <header className="relative overflow-hidden rounded-2xl border border-fg-3">
        <div
          aria-hidden
          className="absolute inset-0"
          style={{ backgroundColor: genre.color_hex, opacity: 0.25 }}
        />
        <div
          aria-hidden
          className="absolute inset-0 bg-linear-to-br from-bg-0/80 via-bg-0/70 to-bg-0/85"
        />
        <div className="relative px-6 py-10 sm:px-10">
          <p className="font-mono text-[11px] uppercase tracking-widest text-fg-2">
            {name}
          </p>
          <h1 className="mt-2 font-display text-[clamp(2.25rem,5vw,3.75rem)] font-semibold leading-tight text-fg-0">
            {t('comboTitle', { genre: genre.name, name })}
          </h1>
          <p className="mt-3 max-w-2xl text-fg-1">
            {t('comboIntro', {
              genre: genre.name,
              name,
              count: facet.station_count,
            })}
          </p>
        </div>
      </header>

      <div className="space-y-4">
        <StationGrid
          stations={stationsPage.items}
          genresBySlug={genresBySlug}
          maxCols={3}
          labels={{
            curated: tCommon('curated'),
            location: ({ city, country: c }) =>
              tStation('location', { city, country: c }),
            empty: t('stationCount', { count: 0 }),
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

      <JsonLd data={breadcrumbLd} />
      <JsonLd data={collectionLd} />
    </div>
  );
}
