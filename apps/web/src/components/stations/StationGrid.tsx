import type { StationSummary, Genre } from '@/lib/types';
import { StationCard } from './StationCard';

interface Props {
  stations: StationSummary[];
  genresBySlug: Record<string, Genre>;
  labels: {
    curated: string;
    location: (values: { city: string; country: string }) => string;
    empty: string;
  };
  /**
   * Max number of columns at lg+. Defaults to 3 (no-sidebar pages).
   * Genre listing pages render with a 240px sidebar that crushes the
   * 3-col layout below the comfort zone — pass 2 there.
   */
  maxCols?: 2 | 3;
}

export function StationGrid({
  stations,
  genresBySlug,
  labels,
  maxCols = 3,
}: Props) {
  if (stations.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-fg-3 bg-bg-2 p-10 text-center">
        <span
          aria-hidden
          className="mb-3 inline-flex h-12 w-12 -rotate-1 items-center justify-center rounded-full bg-wave-soft font-display text-xl font-bold text-wave shadow-sticker"
        >
          ♪
        </span>
        <p className="font-display text-lg text-fg-1">{labels.empty}</p>
      </div>
    );
  }

  const gridCols =
    maxCols === 2
      ? 'grid grid-cols-1 gap-4 sm:grid-cols-2'
      : 'grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3';

  return (
    <div className={gridCols}>
      {stations.map((s, i) => (
        <StationCard
          key={s.id}
          station={s}
          genresBySlug={genresBySlug}
          index={i}
          labels={{ curated: labels.curated, location: labels.location }}
        />
      ))}
    </div>
  );
}
