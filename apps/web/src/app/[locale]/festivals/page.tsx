import type { Metadata } from 'next';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { FestivalCards } from '@/components/festivals/FestivalCards';
import { JsonLd } from '@/components/seo/JsonLd';
import { Link } from '@/i18n/navigation';
import { festivalCalendarUrl, getAllUpcomingFestivals, type Festival } from '@/lib/festivals';
import { NOINDEX_FOLLOW } from '@/lib/indexability';
import { buildAlternates } from '@/lib/seo';
import { SITE_URL } from '@/lib/site';

export const revalidate = 3600;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: 'festivals' });
  return {
    title: t('indexMetaTitle'),
    description: t('indexIntro'),
    alternates: buildAlternates(locale, '/festivals'),
    // El calendario vive en gofestivals.eu (ADR 015).
    robots: NOINDEX_FOLLOW,
  };
}

/** Agrupa por mes de inicio (UTC, como las fechas de la API), conservando el orden. */
function groupByMonth(festivals: Festival[], locale: string): Array<[string, Festival[]]> {
  const fmt = new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric', timeZone: 'UTC' });
  const groups = new Map<string, Festival[]>();
  for (const f of festivals) {
    const key = fmt.format(new Date(f.startDate));
    groups.set(key, [...(groups.get(key) ?? []), f]);
  }
  return [...groups.entries()];
}

export default async function FestivalsIndexPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations('festivals');
  const festivals = await getAllUpcomingFestivals();

  const breadcrumbLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: t('home'), item: `${SITE_URL}/${locale}` },
      { '@type': 'ListItem', position: 2, name: t('crumb'), item: `${SITE_URL}/${locale}/festivals` },
    ],
  };

  return (
    <div className="space-y-10">
      <nav className="flex items-center gap-2 font-mono text-[12px] uppercase tracking-widest text-fg-2">
        <Link href="/" className="-my-2 py-2 transition-colors hover:text-fg-0">
          {t('home')}
        </Link>
        <span>/</span>
        <span className="text-fg-1">{t('crumb')}</span>
      </nav>
      <header className="space-y-3">
        <h1 className="font-display text-[clamp(2rem,6vw,3.5rem)] font-semibold leading-[1.05] text-fg-0">
          {t('indexTitle')}
        </h1>
        <p className="max-w-prose text-fg-2">{t('indexIntro')}</p>
      </header>

      {festivals.length === 0 ? (
        <p className="text-fg-2">{t('empty')}</p>
      ) : (
        groupByMonth(festivals, locale).map(([month, items]) => (
          <section key={month} className="space-y-4">
            <h2 className="font-display text-xl font-semibold capitalize text-fg-0">{month}</h2>
            <FestivalCards festivals={items} locale={locale} />
          </section>
        ))
      )}

      <p>
        <a
          href={festivalCalendarUrl(locale)}
          className="inline-flex min-h-11 items-center font-mono text-[12px] uppercase tracking-widest text-fg-2 transition-colors hover:text-fg-0"
        >
          {t('fullCalendar')} →
        </a>
      </p>
      <JsonLd data={breadcrumbLd} />
    </div>
  );
}
