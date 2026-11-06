import { notFound } from 'next/navigation';
import type { Metadata } from 'next';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Link } from '@/i18n/navigation';
import { getCountryFacets, getGenresTree, listStations } from '@/lib/api';
import { StationGrid } from '@/components/stations/StationGrid';
import { UpcomingFestivals } from '@/components/festivals/UpcomingFestivals';
import { getUpcomingFestivals } from '@/lib/festivals';
import { SidebarFilters } from '@/components/layout/SidebarFilters';
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
  searchParams,
}: {
  params: Promise<{ locale: string; slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}): Promise<Metadata> {
  const { locale, slug } = await params;
  const sp = await searchParams;
  const tGenres = await getTranslations({ locale, namespace: 'genres' });
  const tHome = await getTranslations({ locale, namespace: 'home' });
  const tPagination = await getTranslations({
    locale,
    namespace: 'pagination',
  });
  const pageParam = typeof sp.page === 'string' ? parseInt(sp.page, 10) : 1;
  const page = Number.isFinite(pageParam) && pageParam > 0 ? pageParam : 1;
  const countryParam = typeof sp.country === 'string' ? sp.country : undefined;
  const hasFilters = countryParam !== undefined || sp.curated !== undefined;
  // Paginación limpia: self-canonical con título "página N" (las páginas
  // profundas listan emisoras que ningún otro sitio enlaza). Con
  // ?country=… el canonical apunta al combo dedicado si pasa el gate;
  // si no, a la página 1 limpia del género.
  let canonicalPath =
    !hasFilters && page > 1 ? `/genres/${slug}?page=${page}` : `/genres/${slug}`;
  if (countryParam) {
    const facets = await getCountryFacets({ genre: slug }).catch(() => []);
    const facet = facets.find(
      (f) => f.code.toLowerCase() === countryParam.toLowerCase(),
    );
    if (facet && facet.station_count >= COMBO_GATE_MIN_STATIONS) {
      canonicalPath = `/countries/${facet.code.toLowerCase()}/${slug}`;
    }
  }
  const alternates = buildAlternates(locale, canonicalPath);
  const pageSuffix =
    !hasFilters && page > 1 ? tPagination('pageSuffix', { page }) : '';
  const url = `${SITE_URL}/${locale}/genres/${slug}`;
  try {
    const genres = await getGenresTree();
    const genre = indexBySlug(genres)[slug];
    if (!genre) return { alternates };
    const title =
      tGenres('metaTitle', {
        name: genre.name,
        count: genre.station_count,
      }) + pageSuffix;
    const description = tGenres('metaDescription', {
      name: genre.name,
      count: genre.station_count,
    });
    return {
      title,
      description,
      alternates,
      openGraph: {
        type: 'website',
        title,
        description,
        url,
        locale,
        siteName: tHome('title'),
      },
      twitter: {
        card: 'summary_large_image',
        title,
        description,
      },
    };
  } catch {
    return { alternates };
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

  const parent =
    genre.parent_id === null
      ? null
      : (Object.values(genresBySlug).find((g) => g.id === genre.parent_id) ?? null);
  const subgenres = genre.children.filter((c) => c.station_count > 0);

  const country = typeof sp.country === 'string' ? sp.country : undefined;
  const curatedParam = typeof sp.curated === 'string' ? sp.curated : undefined;
  const page = typeof sp.page === 'string' ? parseInt(sp.page, 10) : 1;

  const tGenres = await getTranslations('genres');
  const tCommon = await getTranslations('common');
  const tStation = await getTranslations('station');
  const tHome = await getTranslations('home');
  const tNav = await getTranslations('nav');
  const tPagination = await getTranslations('pagination');
  const tFestivals = await getTranslations('festivals');

  // Festivales solo en la primera página y sin filtro de país: evita repetir el
  // módulo en cada paginación y mostrarlo recortado por el backfill de países.
  const showFestivals = (Number.isFinite(page) ? page : 1) <= 1 && !country;
  const [stationsPage, countryFacets, festivals] = await Promise.all([
    listStations({
      genre: genre.slug,
      country,
      curated: curatedParam === 'true' ? true : undefined,
      page: Number.isFinite(page) && page > 0 ? page : 1,
      size: 20,
      revalidate: 300,
    }),
    getCountryFacets({ genre: genre.slug }).catch(() => []),
    showFestivals
      ? getUpcomingFestivals({ genre: genre.slug })
      : Promise.resolve([]),
  ]);

  // Países reales del género (antes lista hardcodeada con 'UK' no-ISO).
  const countries = countryFacets.slice(0, 12).map((f) => f.code);
  // Países con combo dedicado: el sidebar navega a la ruta indexable en
  // lugar de filtrar por querystring (y los enlaces de abajo la enlazan).
  const comboFacets = countryFacets.filter(
    (f) => f.station_count >= COMBO_GATE_MIN_STATIONS,
  );
  const countryRoutes: Record<string, string> = Object.fromEntries(
    comboFacets.map((f) => [
      f.code,
      `/countries/${f.code.toLowerCase()}/${genre.slug}`,
    ]),
  );

  const buildPageHref = (targetPage: number): string => {
    const params = new URLSearchParams();
    if (country) params.set('country', country);
    if (curatedParam) params.set('curated', curatedParam);
    if (targetPage > 1) params.set('page', String(targetPage));
    const qs = params.toString();
    return `/${locale}/genres/${slug}${qs ? `?${qs}` : ''}`;
  };

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
        name: tGenres('title'),
        item: `${SITE_URL}/${locale}/genres`,
      },
      ...(parent
        ? [
            {
              '@type': 'ListItem',
              position: 3,
              name: parent.name,
              item: `${SITE_URL}/${locale}/genres/${parent.slug}`,
            },
          ]
        : []),
      { '@type': 'ListItem', position: parent ? 4 : 3, name: genre.name },
    ],
  };
  const collectionLd = {
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    name: tGenres('exploreTitle', { name: genre.name }),
    url: `${SITE_URL}/${locale}/genres/${slug}`,
    inLanguage: locale,
    mainEntity: {
      '@type': 'ItemList',
      numberOfItems: stationsPage.total,
      itemListElement: stationsPage.items.map((s, i) => ({
        '@type': 'ListItem',
        position: i + 1,
        name: s.name,
        url: `${SITE_URL}/${locale}/stations/${s.slug}`,
      })),
    },
  };

  return (
    <div className="space-y-8">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 font-mono text-[12px] uppercase tracking-widest text-fg-2">
        <Link href="/" className="-my-2 py-2 transition-colors hover:text-fg-0">
          {tNav('home')}
        </Link>
        <span>/</span>
        <span className="text-fg-1">{tGenres('title')}</span>
        {parent && (
          <>
            <span>/</span>
            <Link
              href={`/genres/${parent.slug}`}
              className="-my-2 py-2 transition-colors hover:text-fg-0"
            >
              {parent.name}
            </Link>
          </>
        )}
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
          className="absolute inset-0 bg-linear-to-br from-bg-0/80 via-bg-0/70 to-bg-0/85"
        />
        <div className="relative px-6 py-10 sm:px-10">
          <p className="font-mono text-[12px] uppercase tracking-widest text-fg-2">
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

      {subgenres.length > 0 && (
        <nav aria-label={tGenres('subgenres')} className="space-y-2">
          <p className="font-mono text-[12px] uppercase tracking-widest text-fg-2">
            {tGenres('subgenres')}
          </p>
          <ul className="flex flex-wrap gap-2">
            {subgenres.map((c) => (
              <li key={c.slug}>
                <Link
                  href={`/genres/${c.slug}`}
                  className="inline-block rounded-full border border-fg-3 px-3 py-1.5 font-mono text-[12px] uppercase tracking-wide text-fg-1 transition-colors hover:border-fg-2 hover:text-fg-0"
                >
                  {c.name} · {c.station_count}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      )}

      <div className="grid grid-cols-1 gap-6 md:grid-cols-[240px_1fr]">
        <SidebarFilters
          current={{ country, curated: curatedParam === 'true' }}
          countries={countries}
          countryRoutes={countryRoutes}
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

      <UpcomingFestivals
        festivals={festivals}
        locale={locale}
        labels={{
          title: tFestivals('title', { name: genre.name }),
          viewAll: tFestivals('viewAll'),
          source: tFestivals('source'),
        }}
      />

      {comboFacets.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-display text-xl font-semibold text-fg-0">
            {tGenres('byCountry', { name: genre.name })}
          </h2>
          <ul className="flex flex-wrap gap-2">
            {comboFacets.slice(0, 8).map((f) => (
              <li key={f.code}>
                <Link
                  href={`/countries/${f.code.toLowerCase()}/${genre.slug}`}
                  className="inline-flex items-center gap-2 rounded-full border border-fg-3 bg-bg-2 px-3 py-1.5 font-mono text-xs uppercase tracking-wide text-fg-1 transition-colors hover:border-fg-2 hover:bg-bg-3"
                >
                  {regionName(locale, f.code)} ({f.station_count})
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <JsonLd data={breadcrumbLd} />
      <JsonLd data={collectionLd} />
    </div>
  );
}
