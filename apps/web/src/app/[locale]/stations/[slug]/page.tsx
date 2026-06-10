import { notFound } from 'next/navigation';
import type { Metadata } from 'next';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Link } from '@/i18n/navigation';
import { getGenresTree, getStation } from '@/lib/api';
import { getSimilarStations } from '@/lib/recs';
import { StationPlayerControls } from '@/components/stations/StationPlayerControls';
import { TrackedStationGrid } from '@/components/stations/TrackedStationGrid';
import { NowPlaying } from '@/components/player/NowPlaying';
import { HeartButton } from '@/components/auth/HeartButton';
import { LikeButton } from '@/components/auth/LikeButton';
import { Badge } from '@/components/ui/badge';
import { JsonLd } from '@/components/seo/JsonLd';
import { initials } from '@/lib/utils';
import { SITE_URL } from '@/lib/site';
import { buildAlternates } from '@/lib/seo';

export const revalidate = 60;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}): Promise<Metadata> {
  const { locale, slug } = await params;
  const alternates = buildAlternates(locale, `/stations/${slug}`);
  const tHome = await getTranslations({ locale, namespace: 'home' });
  const tStation = await getTranslations({ locale, namespace: 'station' });
  const station = await getStation(slug);
  if (!station) return { alternates };
  const url = `${SITE_URL}/${locale}/stations/${slug}`;
  const genreName = station.genres[0]?.name;
  const place =
    station.city && station.country_code
      ? tStation('location', {
          city: station.city,
          country: station.country_code,
        })
      : (station.city ?? station.country_code ?? '');
  const details = [genreName, place].filter(Boolean).join(' · ');
  const description = tStation('metaDescription', {
    name: station.name,
    details: details || '—',
    hasDetails: details ? 'yes' : 'no',
  });
  return {
    title: station.name,
    description,
    alternates,
    openGraph: {
      type: 'website',
      title: station.name,
      description,
      url,
      locale,
      siteName: tHome('title'),
    },
    twitter: {
      card: 'summary_large_image',
      title: station.name,
      description,
    },
  };
}

export default async function StationPage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale, slug } = await params;
  setRequestLocale(locale);

  const station = await getStation(slug);
  if (!station) notFound();

  const tStation = await getTranslations('station');
  const tCommon = await getTranslations('common');
  const tNav = await getTranslations('nav');

  // No personalizado → puede ir en el ISR. La tabla de similitud se
  // regenera de noche; si aún no existe para esta emisora, sección fuera.
  const [similar, genresTree] = await Promise.all([
    getSimilarStations(slug, { size: 6, revalidate: 3600 }).catch(() => []),
    getGenresTree().catch(() => []),
  ]);
  const genresBySlug: Record<string, (typeof genresTree)[number]> = {};
  const walkGenres = (list: typeof genresTree) => {
    for (const g of list) {
      genresBySlug[g.slug] = g;
      walkGenres(g.children);
    }
  };
  walkGenres(genresTree);

  const primaryColor = station.genres[0]?.color_hex ?? '#8B4EE8';

  const primaryStream =
    station.streams.find((s) => s.is_primary) ?? station.streams[0] ?? null;
  const baseSummary = {
    id: station.id,
    slug: station.slug,
    name: station.name,
    country_code: station.country_code,
    city: station.city,
    curated: station.curated,
    quality_score: station.quality_score,
    votes_local: station.votes_local ?? 0,
    genres: station.genres.map((g) => g.slug),
    is_favorite: station.is_favorite ?? null,
    user_voted: station.user_voted ?? null,
  };

  const stationUrl = `${SITE_URL}/${locale}/stations/${station.slug}`;
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
      { '@type': 'ListItem', position: 2, name: station.name },
    ],
  };
  // Radio-Browser stores `language` as a free-text, comma-joined string
  // (e.g. "english,română"). Split it so inLanguage is a proper list
  // instead of one invalid blob.
  const languages = (station.language ?? '')
    .split(',')
    .map((l) => l.trim())
    .filter(Boolean);
  const radioStationLd = {
    '@context': 'https://schema.org',
    '@type': 'RadioStation',
    name: station.name,
    url: stationUrl,
    description: [station.name, station.city, station.country_code]
      .filter(Boolean)
      .join(' · '),
    ...(station.homepage_url ? { sameAs: station.homepage_url } : {}),
    ...(station.city || station.country_code
      ? {
          address: {
            '@type': 'PostalAddress',
            ...(station.city ? { addressLocality: station.city } : {}),
            ...(station.country_code
              ? { addressCountry: station.country_code }
              : {}),
          },
        }
      : {}),
    ...(languages.length
      ? { inLanguage: languages.length === 1 ? languages[0] : languages }
      : {}),
  };

  return (
    <div className="space-y-10">
      <nav className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-fg-2">
        <Link href="/" className="transition-colors hover:text-fg-0">
          {tNav('home')}
        </Link>
        <span>/</span>
        <span className="text-fg-1 truncate">{station.name}</span>
      </nav>

      <section className="flex flex-col items-start gap-8 sm:flex-row">
        <div
          className="flex h-44 w-44 shrink-0 -rotate-1 items-center justify-center rounded-2xl font-display text-6xl font-semibold text-bg-0 shadow-sticker-lg"
          style={{ backgroundColor: primaryColor }}
        >
          {initials(station.name)}
        </div>
        <div className="flex-1 space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            {station.curated && (
              <Badge tone="magenta" sticker>
                {tCommon('curated')}
              </Badge>
            )}
            {station.genres.map((g) => (
              <Badge
                key={g.slug}
                className="border-fg-3 bg-bg-2"
                style={{ color: g.color_hex }}
              >
                {g.name}
              </Badge>
            ))}
          </div>
          <h1 className="font-display text-[clamp(2rem,5vw,3.5rem)] font-semibold leading-[1.05] text-fg-0">
            {station.name}
          </h1>
          {(station.city || station.country_code) && (
            <p className="font-mono text-sm uppercase tracking-wide text-fg-2">
              {station.city ?? ''}
              {station.city && station.country_code ? ' · ' : ''}
              {station.country_code ?? ''}
              {primaryStream?.codec && primaryStream.bitrate && (
                <span className="ml-3 text-fg-2/80">
                  {primaryStream.codec.toUpperCase()} · {primaryStream.bitrate}kbps
                </span>
              )}
            </p>
          )}
          <div className="flex flex-wrap items-center gap-3 pt-2">
            <StationPlayerControls
              baseSummary={baseSummary}
              streams={station.streams}
              color={primaryColor}
            />
            <LikeButton
              stationId={station.id}
              initialUserVoted={station.user_voted ?? null}
              initialVotesLocal={station.votes_local ?? 0}
              size="md"
            />
            <HeartButton
              stationId={station.id}
              initialIsFavorite={station.is_favorite ?? null}
              size="md"
            />
          </div>
        </div>
      </section>

      <section className="relative overflow-hidden rounded-2xl border border-fg-3 bg-bg-2 p-6">
        <h2 className="mb-4 font-mono text-[11px] font-semibold uppercase tracking-widest text-fg-2">
          <span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-cyan align-middle" />
          {tStation('nowPlaying')}
        </h2>
        <NowPlaying slug={station.slug} size="lg" />
      </section>

      {station.now_playing.length > 0 && (
        <section>
          <h2 className="mb-4 font-display text-xl font-semibold text-fg-0">
            {tStation('recentTracks')}
          </h2>
          <ul className="overflow-hidden rounded-xl border border-fg-3 divide-y divide-fg-3/50">
            {station.now_playing.map((entry, i) => (
              <li
                key={`${entry.captured_at}-${i}`}
                className="flex items-baseline justify-between gap-4 bg-bg-2 px-5 py-3 transition-colors hover:bg-bg-3"
              >
                <span className="min-w-0 truncate text-fg-1">
                  <span className="font-medium text-fg-0">
                    {entry.title ?? tStation('noMetadata')}
                  </span>
                  {entry.artist && (
                    <span className="ml-2 text-fg-2">
                      {tCommon('by')} {entry.artist}
                    </span>
                  )}
                </span>
                <time className="shrink-0 font-mono text-[11px] uppercase text-fg-2">
                  {new Date(entry.captured_at).toLocaleTimeString(locale)}
                </time>
              </li>
            ))}
          </ul>
        </section>
      )}

      {similar.length > 0 && (
        <section className="space-y-5">
          <h2 className="font-display text-xl font-semibold text-fg-0">
            {tStation('similarTitle')}
          </h2>
          <TrackedStationGrid
            stations={similar}
            genresBySlug={genresBySlug}
            surface="station_similar"
          />
        </section>
      )}

      <JsonLd data={breadcrumbLd} />
      <JsonLd data={radioStationLd} />
    </div>
  );
}
