import type { Metadata } from 'next';
import { notFound, permanentRedirect } from 'next/navigation';
import { getFormatter, getTranslations, setRequestLocale } from 'next-intl/server';
import { FestivalGenreLinks } from '@/components/festivals/FestivalGenreLinks';
import { FestivalHero } from '@/components/festivals/FestivalHero';
import { JsonLd } from '@/components/seo/JsonLd';
import { StationGrid } from '@/components/stations/StationGrid';
import { Link } from '@/i18n/navigation';
import { getGenresTree } from '@/lib/api';
import { festivalEventLd } from '@/lib/festival-jsonld';
import { festivalGenreWeights, rollUpToRoots } from '@/lib/festival-genres';
import { stationsForFestival } from '@/lib/festival-stations';
import {
  festivalPath,
  festivalPhase,
  formatFestivalDates,
  getFestival,
} from '@/lib/festivals';
import { indexGenresBySlug } from '@/lib/genre-index';
import { buildAlternates, regionName } from '@/lib/seo';
import { SITE_URL } from '@/lib/site';

export const revalidate = 3600;

type Params = { locale: string; id: string; slug?: string[] };
const DEFAULT_COLOR = '#8B4EE8';

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { locale, id } = await params;
  const festival = await getFestival(id);
  if (!festival) return {};
  const t = await getTranslations({ locale, namespace: 'festivals' });
  const year = new Date(festival.startDate).getUTCFullYear();
  const details = formatFestivalDates(locale, festival.startDate, festival.endDate);
  const genres = festival.genres.slice(0, 3).join(', ');
  const title = t('pageTitle', { name: festival.name, year });
  const description = genres
    ? t('pageDescription', { name: festival.name, details, genres })
    : t('pageDescriptionPlain', { name: festival.name, details });
  const path = festivalPath(festival);
  return {
    title,
    description,
    alternates: buildAlternates(locale, path),
    // Una edición ya celebrada sigue siendo útil para quien llega, pero no merece indexarse.
    ...(festivalPhase(festival) === 'ended' ? { robots: { index: false, follow: true } } : {}),
    // openGraph propio anula la imagen heredada del file convention: se indica la de marca.
    openGraph: {
      title,
      description,
      url: `${SITE_URL}/${locale}${path}`,
      type: 'website',
      images: [{ url: `${SITE_URL}/${locale}/opengraph-image`, width: 1200, height: 630 }],
    },
  };
}

export default async function FestivalPage({ params }: { params: Promise<Params> }) {
  const { locale, id, slug } = await params;
  setRequestLocale(locale);

  const festival = await getFestival(id);
  if (!festival) notFound();
  // Una sola URL por festival: sin slug, con slug equivocado o con ceros a la izquierda → canónica.
  const canonical = festivalPath(festival);
  if (`/festivals/${id}/${slug?.join('/') ?? ''}` !== canonical) {
    permanentRedirect(`/${locale}${canonical}`);
  }

  const [t, tCommon, tStation, tHome, format, genreTree] = await Promise.all([
    getTranslations('festivals'),
    getTranslations('common'),
    getTranslations('station'),
    getTranslations('home'),
    getFormatter(),
    getGenresTree(),
  ]);
  const genresBySlug = indexGenresBySlug(genreTree);
  const weights = festivalGenreWeights(festival.genres, new Set(Object.keys(genresBySlug)));
  // Las emisoras se reparten por género raíz (pedir `house` ya incluye `deep-house`).
  const stations = await stationsForFestival(rollUpToRoots(weights, genresBySlug), 6);

  const phase = festivalPhase(festival);
  const phaseLabel =
    phase === 'upcoming'
      ? t('startsIn', { relative: format.relativeTime(new Date(festival.startDate), new Date()) })
      : phase === 'ongoing'
        ? t('ongoing')
        : t('ended');
  const mainGenres = weights.slice(0, 6).flatMap((w) => genresBySlug[w.slug] ?? []);
  const color = mainGenres[0]?.color_hex ?? DEFAULT_COLOR;

  const eventLd = festivalEventLd(festival, locale);
  const breadcrumbLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: t('home'), item: `${SITE_URL}/${locale}` },
      { '@type': 'ListItem', position: 2, name: t('crumb'), item: `${SITE_URL}/${locale}/festivals` },
      { '@type': 'ListItem', position: 3, name: festival.name, item: `${SITE_URL}/${locale}${canonical}` },
    ],
  };

  return (
    <div className="space-y-10">
      <nav className="flex items-center gap-2 font-mono text-[12px] uppercase tracking-widest text-fg-2">
        <Link href="/" className="-my-2 py-2 transition-colors hover:text-fg-0">
          {t('home')}
        </Link>
        <span>/</span>
        <Link href="/festivals" className="-my-2 py-2 transition-colors hover:text-fg-0">
          {t('crumb')}
        </Link>
        <span>/</span>
        <span className="truncate text-fg-1">{festival.name}</span>
      </nav>

      <FestivalHero
        festival={festival}
        locale={locale}
        color={color}
        phase={phase}
        phaseLabel={phaseLabel}
        countryName={festival.countryCode ? regionName(locale, festival.countryCode) : null}
        labels={{ viewOnGofestivals: t('viewOnGofestivals'), officialSite: t('officialSite') }}
      />

      <FestivalGenreLinks title={t('genresTitle')} genres={mainGenres} />

      {stations.length > 0 && (
        <section className="space-y-4">
          <div>
            <h2 className="font-display text-xl font-semibold text-fg-0">{t('warmUpTitle')}</h2>
            <p className="mt-1 text-sm text-fg-2">{t('warmUpIntro')}</p>
          </div>
          <StationGrid
            stations={stations}
            genresBySlug={genresBySlug}
            labels={{
              curated: tCommon('curated'),
              location: ({ city, country }) => tStation('location', { city, country }),
              empty: tHome('featuredEmpty'),
            }}
          />
        </section>
      )}

      <JsonLd data={breadcrumbLd} />
      {eventLd && <JsonLd data={eventLd} />}
    </div>
  );
}
