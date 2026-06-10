import type { Metadata } from 'next';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Link } from '@/i18n/navigation';
import { getGenresTree, listTrendingStations } from '@/lib/api';
import { StationGrid } from '@/components/stations/StationGrid';
import { JsonLd } from '@/components/seo/JsonLd';
import { SITE_URL } from '@/lib/site';
import { buildAlternates, TRENDING_GENRE_GATE_MIN } from '@/lib/seo';
import type { Genre } from '@/lib/types';

export const revalidate = 300;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: 'trending' });
  return {
    title: t('metaTitle'),
    description: t('metaDescription'),
    alternates: buildAlternates(locale, '/trending'),
  };
}

export default async function TrendingPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations('trending');
  const tNav = await getTranslations('nav');
  const tCommon = await getTranslations('common');
  const tStation = await getTranslations('station');

  const [trendingPage, genresTree] = await Promise.all([
    listTrendingStations({ limit: 50 }).catch(() => null),
    getGenresTree().catch(() => []),
  ]);
  const stations = trendingPage?.items ?? [];

  const genresBySlug: Record<string, Genre> = {};
  const walk = (list: Genre[]) => {
    for (const g of list) {
      genresBySlug[g.slug] = g;
      walk(g.children);
    }
  };
  walk(genresTree);

  // Solo géneros raíz con catálogo suficiente para que su ranking no sea thin.
  const genreLinks = genresTree.filter(
    (g) => g.station_count >= TRENDING_GENRE_GATE_MIN,
  );

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
        item: `${SITE_URL}/${locale}/trending`,
      },
    ],
  };
  const itemListLd = {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    name: t('metaTitle'),
    itemListOrder: 'https://schema.org/ItemListOrderDescending',
    numberOfItems: stations.length,
    itemListElement: stations.map((s, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: s.name,
      url: `${SITE_URL}/${locale}/stations/${s.slug}`,
    })),
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
          {t('heading')}
        </h1>
        <p className="mt-3 max-w-2xl text-fg-2">{t('description')}</p>
      </header>

      {genreLinks.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-mono text-[11px] font-semibold uppercase tracking-widest text-fg-2">
            {t('byGenre')}
          </h2>
          <ul className="flex flex-wrap gap-2">
            {genreLinks.map((g) => (
              <li key={g.slug}>
                <Link
                  href={`/trending/${g.slug}`}
                  className="inline-flex items-center gap-2 rounded-full border border-fg-3 bg-bg-2 px-3 py-1.5 font-mono text-xs uppercase tracking-wide text-fg-1 transition-colors hover:border-fg-2 hover:bg-bg-3"
                >
                  <span
                    aria-hidden
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ backgroundColor: g.color_hex }}
                  />
                  {g.name}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {stations.length > 0 ? (
        <StationGrid
          stations={stations}
          genresBySlug={genresBySlug}
          maxCols={3}
          labels={{
            curated: tCommon('curated'),
            location: ({ city, country: c }) =>
              tStation('location', { city, country: c }),
            empty: t('empty'),
          }}
        />
      ) : (
        <p className="text-fg-2">{t('empty')}</p>
      )}

      <JsonLd data={breadcrumbLd} />
      {stations.length > 0 && <JsonLd data={itemListLd} />}
    </div>
  );
}
