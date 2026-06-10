import { notFound } from 'next/navigation';
import type { Metadata } from 'next';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Link } from '@/i18n/navigation';
import {
  getCountryFacets,
  getGenreFacets,
  getGenresTree,
  listStations,
} from '@/lib/api';
import { StationGrid } from '@/components/stations/StationGrid';
import { PublicPagination } from '@/components/PublicPagination';
import { JsonLd } from '@/components/seo/JsonLd';
import { SITE_URL } from '@/lib/site';
import {
  buildAlternates,
  COUNTRY_GATE_MIN_STATIONS,
  regionName,
} from '@/lib/seo';
import type { Genre } from '@/lib/types';

export const revalidate = 300;

async function gatedFacet(code: string) {
  const facets = await getCountryFacets().catch(() => []);
  const facet = facets.find((f) => f.code.toLowerCase() === code.toLowerCase());
  if (!facet || facet.station_count < COUNTRY_GATE_MIN_STATIONS) return null;
  return facet;
}

export async function generateStaticParams() {
  try {
    const facets = await getCountryFacets();
    return facets
      .filter((f) => f.station_count >= COUNTRY_GATE_MIN_STATIONS)
      .map((f) => ({ code: f.code.toLowerCase() }));
  } catch {
    return [];
  }
}

export async function generateMetadata({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string; code: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}): Promise<Metadata> {
  const { locale, code } = await params;
  const sp = await searchParams;
  const t = await getTranslations({ locale, namespace: 'countries' });
  const tPagination = await getTranslations({
    locale,
    namespace: 'pagination',
  });
  const pageParam = typeof sp.page === 'string' ? parseInt(sp.page, 10) : 1;
  const page = Number.isFinite(pageParam) && pageParam > 0 ? pageParam : 1;
  const base = `/countries/${code.toLowerCase()}`;
  const alternates = buildAlternates(
    locale,
    page > 1 ? `${base}?page=${page}` : base,
  );
  const facet = await gatedFacet(code);
  if (!facet) return { alternates };
  const name = regionName(locale, facet.code);
  const pageSuffix = page > 1 ? tPagination('pageSuffix', { page }) : '';
  return {
    title: t('metaTitle', { name, count: facet.station_count }) + pageSuffix,
    description: t('metaDescription', { name, count: facet.station_count }),
    alternates,
  };
}

export default async function CountryPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string; code: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { locale, code } = await params;
  const sp = await searchParams;
  setRequestLocale(locale);

  const facet = await gatedFacet(code);
  if (!facet) notFound();

  const pageParam = typeof sp.page === 'string' ? parseInt(sp.page, 10) : 1;
  const page = Number.isFinite(pageParam) && pageParam > 0 ? pageParam : 1;

  const t = await getTranslations('countries');
  const tNav = await getTranslations('nav');
  const tCommon = await getTranslations('common');
  const tStation = await getTranslations('station');
  const tHome = await getTranslations('home');
  const tPagination = await getTranslations('pagination');

  const [stationsPage, genreFacets, genresTree] = await Promise.all([
    listStations({ country: facet.code, page, size: 20, revalidate: 300 }),
    getGenreFacets({ country: facet.code }).catch(() => []),
    getGenresTree().catch(() => []),
  ]);

  const genresBySlug: Record<string, Genre> = {};
  const walk = (list: Genre[]) => {
    for (const g of list) {
      genresBySlug[g.slug] = g;
      walk(g.children);
    }
  };
  walk(genresTree);

  const name = regionName(locale, facet.code);
  const topGenre = genreFacets[0];
  const codeLower = facet.code.toLowerCase();

  const buildPageHref = (targetPage: number): string =>
    `/${locale}/countries/${codeLower}${targetPage > 1 ? `?page=${targetPage}` : ''}`;

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
    ],
  };
  const collectionLd = {
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    name: t('exploreTitle', { name }),
    url: `${SITE_URL}/${locale}/countries/${codeLower}`,
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
        <span className="text-fg-1">{name}</span>
      </nav>

      <header>
        <h1 className="font-display text-[clamp(2.25rem,5vw,3.75rem)] font-semibold leading-tight text-fg-0">
          {t('exploreTitle', { name })}
        </h1>
        <p className="mt-3 max-w-2xl text-fg-1">
          {t('intro', {
            name,
            count: facet.station_count,
            hasTop: topGenre ? 'yes' : 'no',
            topGenre: topGenre?.name ?? '',
            topCount: topGenre?.station_count ?? 0,
          })}
        </p>
      </header>

      {genreFacets.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-display text-xl font-semibold text-fg-0">
            {t('genresHeading', { name })}
          </h2>
          <ul className="flex flex-wrap gap-2">
            {genreFacets.map((g) => (
              <li key={g.slug}>
                <Link
                  href={`/genres/${g.slug}?country=${facet.code}`}
                  className="inline-flex items-center gap-2 rounded-full border border-fg-3 bg-bg-2 px-3 py-1.5 font-mono text-xs uppercase tracking-wide text-fg-1 transition-colors hover:border-fg-2 hover:bg-bg-3"
                >
                  <span
                    aria-hidden
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ backgroundColor: g.color_hex }}
                  />
                  {g.name} ({g.station_count})
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="space-y-4">
        <h2 className="font-display text-xl font-semibold text-fg-0">
          {t('topStations', { name })}
        </h2>
        <StationGrid
          stations={stationsPage.items}
          genresBySlug={genresBySlug}
          maxCols={3}
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
      </section>

      <JsonLd data={breadcrumbLd} />
      <JsonLd data={collectionLd} />
    </div>
  );
}
