import type { Metadata } from 'next';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Link } from '@/i18n/navigation';
import { listStations } from '@/lib/api';
import { BadgeSnippetGenerator } from '@/components/stations/BadgeSnippetGenerator';
import { JsonLd } from '@/components/seo/JsonLd';
import { SITE_URL } from '@/lib/site';
import { buildAlternates } from '@/lib/seo';

export const revalidate = 3600;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: 'forStations' });
  return {
    title: t('metaTitle'),
    description: t('metaDescription'),
    alternates: buildAlternates(locale, '/for-stations'),
  };
}

export default async function ForStationsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations('forStations');
  const tNav = await getTranslations('nav');

  const total = await listStations({ size: 1, revalidate: 3600 })
    .then((p) => p.total)
    .catch(() => 0);

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
        item: `${SITE_URL}/${locale}/for-stations`,
      },
    ],
  };

  const benefits = [
    { title: t('why1Title'), body: t('why1Body') },
    { title: t('why2Title'), body: t('why2Body') },
    { title: t('why3Title'), body: t('why3Body') },
  ];

  return (
    <div className="space-y-10">
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
        <p className="mt-3 max-w-2xl text-fg-1">
          {t('intro', { count: total })}
        </p>
      </header>

      <section className="grid gap-4 sm:grid-cols-3">
        {benefits.map((b) => (
          <div
            key={b.title}
            className="rounded-2xl border border-fg-3 bg-bg-2 p-5"
          >
            <h2 className="font-display text-lg font-semibold text-fg-0">
              {b.title}
            </h2>
            <p className="mt-2 text-sm text-fg-2">{b.body}</p>
          </div>
        ))}
      </section>

      <section className="space-y-4 rounded-2xl border border-fg-3 bg-bg-2 p-6 sm:p-8">
        <h2 className="font-display text-2xl font-semibold text-fg-0">
          {t('badgeHeading')}
        </h2>
        <p className="max-w-2xl text-fg-2">{t('badgeBody')}</p>
        <BadgeSnippetGenerator />
      </section>

      <p className="text-sm text-fg-2">
        {t('notFoundHint')}{' '}
        <Link
          href="/support"
          className="font-medium text-cyan underline decoration-cyan/40 underline-offset-4 transition-colors hover:text-fg-0"
        >
          {t('contactCta')}
        </Link>
      </p>

      <JsonLd data={breadcrumbLd} />
    </div>
  );
}
