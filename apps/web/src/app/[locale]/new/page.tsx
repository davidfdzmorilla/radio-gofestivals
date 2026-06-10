import type { Metadata } from 'next';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Link } from '@/i18n/navigation';
import { getGenresTree, listNewStations } from '@/lib/api';
import { StationGrid } from '@/components/stations/StationGrid';
import { JsonLd } from '@/components/seo/JsonLd';
import { SITE_URL } from '@/lib/site';
import { buildAlternates } from '@/lib/seo';
import type { Genre } from '@/lib/types';

export const revalidate = 300;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: 'newStations' });
  return {
    title: t('metaTitle'),
    description: t('metaDescription'),
    alternates: buildAlternates(locale, '/new'),
  };
}

export default async function NewStationsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations('newStations');
  const tNav = await getTranslations('nav');
  const tCommon = await getTranslations('common');
  const tStation = await getTranslations('station');

  const [newPage, genresTree] = await Promise.all([
    listNewStations({ limit: 50 }).catch(() => null),
    getGenresTree().catch(() => []),
  ]);
  const stations = newPage?.items ?? [];

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
        item: `${SITE_URL}/${locale}/new`,
      },
    ],
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
    </div>
  );
}
