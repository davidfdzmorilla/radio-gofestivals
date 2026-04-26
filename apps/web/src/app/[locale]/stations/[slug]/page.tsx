import { notFound } from 'next/navigation';
import type { Metadata } from 'next';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { Link } from '@/i18n/navigation';
import { getStation } from '@/lib/api';
import { PlayButton } from '@/components/stations/PlayButton';
import { NowPlaying } from '@/components/player/NowPlaying';
import { Badge } from '@/components/ui/badge';
import { initials } from '@/lib/utils';
import type { StationSummary } from '@/lib/types';

export const revalidate = 60;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const station = await getStation(slug);
  if (!station) return {};
  return {
    title: station.name,
    description: [station.name, station.city, station.country_code]
      .filter(Boolean)
      .join(' · '),
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

  const primaryColor = station.genres[0]?.color_hex ?? '#8B4EE8';

  const primaryStream =
    station.streams.find((s) => s.is_primary) ?? station.streams[0] ?? null;
  const summary: StationSummary = {
    id: station.id,
    slug: station.slug,
    name: station.name,
    country_code: station.country_code,
    city: station.city,
    curated: station.curated,
    quality_score: station.quality_score,
    genres: station.genres.map((g) => g.slug),
    primary_stream: primaryStream,
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
          <div className="pt-2">
            <PlayButton station={summary} color={primaryColor} size="lg" />
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
    </div>
  );
}
