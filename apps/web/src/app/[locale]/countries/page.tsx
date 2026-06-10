import type { Metadata } from 'next';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Link } from '@/i18n/navigation';
import { getCountryFacets } from '@/lib/api';
import { JsonLd } from '@/components/seo/JsonLd';
import { SITE_URL } from '@/lib/site';
import {
  buildAlternates,
  COUNTRY_GATE_MIN_STATIONS,
  regionName,
} from '@/lib/seo';

export const revalidate = 300;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: 'countries' });
  const alternates = buildAlternates(locale, '/countries');
  try {
    const facets = await getCountryFacets();
    const count = facets.filter(
      (f) => f.station_count >= COUNTRY_GATE_MIN_STATIONS,
    ).length;
    return {
      title: t('indexTitle'),
      description: t('indexDescription', { count }),
      alternates,
    };
  } catch {
    return { title: t('indexTitle'), alternates };
  }
}

export default async function CountriesPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations('countries');
  const tNav = await getTranslations('nav');

  const facets = (await getCountryFacets().catch(() => [])).filter(
    (f) => f.station_count >= COUNTRY_GATE_MIN_STATIONS,
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
        item: `${SITE_URL}/${locale}/countries`,
      },
    ],
  };
  const collectionLd = {
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    name: t('indexTitle'),
    url: `${SITE_URL}/${locale}/countries`,
    inLanguage: locale,
    mainEntity: {
      '@type': 'ItemList',
      numberOfItems: facets.length,
      itemListElement: facets.map((f, i) => ({
        '@type': 'ListItem',
        position: i + 1,
        name: regionName(locale, f.code),
        url: `${SITE_URL}/${locale}/countries/${f.code.toLowerCase()}`,
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
        <span className="text-fg-1">{t('title')}</span>
      </nav>

      <header>
        <h1 className="font-display text-[clamp(2.25rem,5vw,3.75rem)] font-semibold leading-tight text-fg-0">
          {t('indexTitle')}
        </h1>
        <p className="mt-3 max-w-2xl text-fg-2">
          {t('indexDescription', { count: facets.length })}
        </p>
      </header>

      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {facets.map((f) => (
          <li key={f.code}>
            <Link
              href={`/countries/${f.code.toLowerCase()}`}
              className="flex h-full flex-col gap-1 rounded-xl border border-fg-3 bg-bg-2 px-4 py-3 transition-colors hover:border-fg-2 hover:bg-bg-3"
            >
              <span className="font-display font-semibold text-fg-0">
                {regionName(locale, f.code)}
              </span>
              <span className="font-mono text-[11px] uppercase tracking-wide text-fg-2">
                {t('stationCount', { count: f.station_count })}
              </span>
            </Link>
          </li>
        ))}
      </ul>

      <JsonLd data={breadcrumbLd} />
      <JsonLd data={collectionLd} />
    </div>
  );
}
