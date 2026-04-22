import { notFound } from 'next/navigation';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { getStation } from '@/lib/api';
import { PlayButton } from '@/components/stations/PlayButton';
import { NowPlaying } from '@/components/player/NowPlaying';
import { Badge } from '@/components/ui/badge';
import { initials } from '@/lib/utils';
import type { StationSummary } from '@/lib/types';

export const revalidate = 60;

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

  const primaryColor = station.genres[0]?.color_hex ?? '#8B4EE8';

  const summary: StationSummary = {
    id: station.id,
    slug: station.slug,
    name: station.name,
    country_code: station.country_code,
    city: station.city,
    codec: station.codec,
    bitrate: station.bitrate,
    curated: station.curated,
    quality_score: station.quality_score,
    genres: station.genres.map((g) => g.slug),
  };

  return (
    <div className="space-y-8">
      <section className="flex flex-col items-start gap-6 sm:flex-row">
        <div
          className="flex h-40 w-40 shrink-0 items-center justify-center rounded-xl font-display text-5xl font-bold text-white"
          style={{ backgroundColor: primaryColor }}
        >
          {initials(station.name)}
        </div>
        <div className="flex-1 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            {station.curated && (
              <Badge className="border-wave/50 bg-wave/20 text-wave-50">
                {tCommon('curated')}
              </Badge>
            )}
            {station.genres.map((g) => (
              <Badge key={g.slug} style={{ color: g.color_hex }}>
                {g.name}
              </Badge>
            ))}
          </div>
          <h1 className="font-display text-4xl font-bold text-white">
            {station.name}
          </h1>
          {(station.city || station.country_code) && (
            <p className="text-white/60">
              {station.city ?? ''}
              {station.city && station.country_code ? ', ' : ''}
              {station.country_code ?? ''}
            </p>
          )}
          <div className="pt-2">
            <PlayButton station={summary} color={primaryColor} />
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-white/10 bg-white/5 p-6">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-white/60">
          {tStation('nowPlaying')}
        </h2>
        <NowPlaying slug={station.slug} size="lg" />
      </section>

      {station.now_playing.length > 0 && (
        <section>
          <h2 className="mb-3 font-display text-xl font-semibold text-white">
            {tStation('recentTracks')}
          </h2>
          <ul className="divide-y divide-white/5 rounded-lg border border-white/10">
            {station.now_playing.map((entry, i) => (
              <li
                key={`${entry.captured_at}-${i}`}
                className="flex items-baseline justify-between px-4 py-3"
              >
                <span className="text-white">
                  {entry.title ?? tStation('noMetadata')}
                  {entry.artist && (
                    <span className="ml-2 text-white/60">
                      {tCommon('by')} {entry.artist}
                    </span>
                  )}
                </span>
                <time className="shrink-0 font-mono text-xs text-white/40">
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
