import { Link } from '@/i18n/navigation';
import { Badge } from '@/components/ui/badge';
import { cn, initials } from '@/lib/utils';
import type { StationSummary, Genre } from '@/lib/types';
import { PlayButton } from './PlayButton';

interface Props {
  station: StationSummary;
  genresBySlug: Record<string, Genre>;
  index?: number;
  labels: {
    curated: string;
    location: (values: { city: string; country: string }) => string;
  };
}

const hoverRotations = ['hover:-rotate-0.5', 'hover:rotate-0.5'];

export function StationCard({ station, genresBySlug, index = 0, labels }: Props) {
  const firstGenreSlug = station.genres.find((slug) => genresBySlug[slug]);
  const firstGenre = firstGenreSlug ? genresBySlug[firstGenreSlug] : undefined;
  const color = firstGenre?.color_hex ?? '#8B4EE8';
  const loc =
    station.city && station.country_code
      ? labels.location({ city: station.city, country: station.country_code })
      : (station.country_code ?? '—');

  const rotationHover = hoverRotations[index % hoverRotations.length]!;

  return (
    <div
      className={cn(
        'group relative flex items-center gap-4 rounded-xl border border-fg-3/50 bg-bg-2 p-4 transition-all duration-200',
        'hover:-translate-y-0.5 hover:border-fg-3 hover:bg-bg-3 hover:shadow-sticker-lg',
        rotationHover,
        'animate-card',
      )}
      style={{ animationDelay: `${Math.min(index * 50, 400)}ms` }}
    >
      <Link
        href={`/stations/${station.slug}`}
        className="flex min-w-0 flex-1 items-center gap-4 outline-none"
      >
        <div
          className="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg font-display text-xl font-bold text-bg-0 shadow-sticker-sm"
          style={{ backgroundColor: color }}
        >
          {initials(station.name)}
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="truncate font-display text-[15px] font-semibold text-fg-0">
            {station.name}
          </h3>
          <p className="truncate font-mono text-[11px] uppercase tracking-wide text-fg-2">
            {loc}
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            {station.curated && (
              <Badge tone="magenta" sticker>
                {labels.curated}
              </Badge>
            )}
            {station.genres.slice(0, 2).map((slug) => {
              const g = genresBySlug[slug];
              if (!g) return null;
              return (
                <Badge
                  key={slug}
                  className="border-fg-3 bg-bg-3"
                  style={{ color: g.color_hex }}
                >
                  {g.name}
                </Badge>
              );
            })}
          </div>
        </div>
      </Link>
      <PlayButton station={station} color={color} size="sm" />
    </div>
  );
}
