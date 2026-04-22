import { Link } from '@/i18n/navigation';
import { Badge } from '@/components/ui/badge';
import { cn, initials } from '@/lib/utils';
import type { StationSummary, Genre } from '@/lib/types';
import { PlayButton } from './PlayButton';

interface Props {
  station: StationSummary;
  genresBySlug: Record<string, Genre>;
  labels: {
    curated: string;
    location: (values: { city: string; country: string }) => string;
  };
}

export function StationCard({ station, genresBySlug, labels }: Props) {
  const firstGenre = station.genres.find((slug) => genresBySlug[slug]);
  const color = firstGenre ? genresBySlug[firstGenre]?.color_hex : '#8B4EE8';
  const loc =
    station.city && station.country_code
      ? labels.location({ city: station.city, country: station.country_code })
      : (station.country_code ?? '—');

  return (
    <div
      className={cn(
        'group relative flex items-center gap-4 rounded-lg border border-white/10 bg-white/5 p-4 transition-colors hover:border-white/30 hover:bg-white/10',
      )}
    >
      <Link
        href={`/stations/${station.slug}`}
        className="flex flex-1 items-center gap-4 min-w-0"
      >
        <div
          className="flex h-14 w-14 shrink-0 items-center justify-center rounded-md font-display text-lg font-bold text-white"
          style={{ backgroundColor: color }}
        >
          {initials(station.name)}
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="truncate font-display font-semibold text-white">
            {station.name}
          </h3>
          <p className="truncate text-sm text-white/60">{loc}</p>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            {station.curated && (
              <Badge className="border-wave/50 bg-wave/20 text-wave-50">
                {labels.curated}
              </Badge>
            )}
            {station.genres.slice(0, 2).map((slug) => {
              const g = genresBySlug[slug];
              if (!g) return null;
              return (
                <Badge
                  key={slug}
                  className="border-white/20 bg-white/5"
                  style={{ color: g.color_hex }}
                >
                  {g.name}
                </Badge>
              );
            })}
          </div>
        </div>
      </Link>
      <PlayButton station={station} color={color ?? '#8B4EE8'} />
    </div>
  );
}
