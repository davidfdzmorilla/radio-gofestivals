import { notFound } from 'next/navigation';
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

function findGenre(genres: Genre[], slug: string): Genre | null {
  for (const g of genres) {
    if (g.slug === slug) return g;
    const child = findGenre(g.children, slug);
    if (child) return child;
  }
  return null;
}

export async function generateStaticParams() {
  try {
    const genres = await getGenresTree();
    return genres
      .filter(
        (g) =>
          g.parent_id === null && g.station_count >= TRENDING_GENRE_GATE_MIN,
      )
      .map((g) => ({ genre: g.slug }));
  } catch {
    return [];
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string; genre: string }>;
}): Promise<Metadata> {
  const { locale, genre: slug } = await params;
  const t = await getTranslations({ locale, namespace: 'trending' });
  const alternates = buildAlternates(locale, `/trending/${slug}`);
  const genre = await getGenresTree()
    .then((tree) => findGenre(tree, slug))
    .catch(() => null);
  if (!genre) return { alternates };
  return {
    title: t('genreMetaTitle', { name: genre.name }),
    description: t('genreMetaDescription', { name: genre.name }),
    alternates,
  };
}

export default async function TrendingGenrePage({
  params,
}: {
  params: Promise<{ locale: string; genre: string }>;
}) {
  const { locale, genre: slug } = await params;
  setRequestLocale(locale);

  const genresTree = await getGenresTree().catch(() => []);
  const genre = findGenre(genresTree, slug);
  if (!genre || genre.station_count < TRENDING_GENRE_GATE_MIN) notFound();

  const t = await getTranslations('trending');
  const tNav = await getTranslations('nav');
  const tCommon = await getTranslations('common');
  const tStation = await getTranslations('station');

  const trendingPage = await listTrendingStations({
    genre: genre.slug,
    limit: 50,
  }).catch(() => null);
  const stations = trendingPage?.items ?? [];

  const genresBySlug: Record<string, Genre> = {};
  const walk = (list: Genre[]) => {
    for (const g of list) {
      genresBySlug[g.slug] = g;
      walk(g.children);
    }
  };
  walk(genresTree);

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
      {
        '@type': 'ListItem',
        position: 3,
        name: genre.name,
        item: `${SITE_URL}/${locale}/trending/${genre.slug}`,
      },
    ],
  };
  const itemListLd = {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    name: t('genreMetaTitle', { name: genre.name }),
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
        <Link href="/trending" className="transition-colors hover:text-fg-0">
          {t('title')}
        </Link>
        <span>/</span>
        <span className="text-fg-1">{genre.name}</span>
      </nav>

      <header>
        <p className="font-mono text-[11px] uppercase tracking-widest text-fg-2">
          {t('title')}
        </p>
        <h1 className="mt-2 font-display text-[clamp(2.25rem,5vw,3.75rem)] font-semibold leading-tight text-fg-0">
          {t('genreHeading', { name: genre.name })}
        </h1>
        <p className="mt-3 max-w-2xl text-fg-2">{t('description')}</p>
      </header>

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
