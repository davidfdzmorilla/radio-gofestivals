import { Link } from '@/i18n/navigation';
import { Badge } from '@/components/ui/badge';
import { HeartButton } from '@/components/auth/HeartButton';
import { LikeButton } from '@/components/auth/LikeButton';
import { readableOnDark } from '@/lib/color';
import { cn } from '@/lib/utils';
import type { StationSummary, Genre } from '@/lib/types';
import { PlayButton } from './PlayButton';
import { StationCover } from './StationCover';

interface Props {
  station: StationSummary;
  genresBySlug: Record<string, Genre>;
  index?: number;
  labels: {
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
        'group relative flex h-full flex-col gap-3 rounded-xl border border-fg-3/50 bg-bg-2 p-4 transition-all duration-200',
        'hover:-translate-y-0.5 hover:border-fg-3 hover:bg-bg-3 hover:shadow-sticker-lg',
        rotationHover,
        'animate-card',
      )}
      style={{ animationDelay: `${Math.min(index * 50, 400)}ms` }}
    >
      <Link
        href={`/stations/${station.slug}`}
        className="flex min-w-0 items-center gap-3 outline-hidden"
      >
        <StationCover
          slug={station.slug}
          name={station.name}
          logoHash={station.logo_hash}
          color={color}
          size="sm"
          className="h-14 w-14 rounded-lg shadow-sticker-sm"
          textClassName="text-xl"
        />
        <div className="min-w-0 flex-1">
          <h3 className="line-clamp-2 font-display text-[15px] font-semibold leading-snug text-fg-0">
            {station.name}
          </h3>
          <p className="truncate font-mono text-[12px] uppercase tracking-wide text-fg-2">
            {loc}
          </p>
        </div>
      </Link>
      {/* Etiquetas a la izquierda y acciones a la derecha, siempre en la base de
          la tarjeta: el título usa todo el ancho y las alturas de una fila coinciden. */}
      <div className="mt-auto flex items-end justify-between gap-3">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">
          {station.genres.slice(0, 2).map((slug) => {
            const g = genresBySlug[slug];
            if (!g) return null;
            return (
              <Badge
                key={slug}
                className="border-fg-3 bg-bg-3"
                style={{ color: readableOnDark(g.color_hex) }}
              >
                {g.name}
              </Badge>
            );
          })}
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <LikeButton
            stationId={station.id}
            initialUserVoted={station.user_voted ?? null}
            initialVotesLocal={station.votes_local ?? 0}
            size="md"
            className="h-11"
          />
          <HeartButton
            stationId={station.id}
            stationSlug={station.slug}
            initialIsFavorite={station.is_favorite ?? null}
            size="md"
            className="h-11 w-11"
          />
          <PlayButton station={station} color={color} size="md" />
        </div>
      </div>
    </div>
  );
}
