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
}

export function StationGrid({ stations, genresBySlug, labels }: Props) {
  if (stations.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-white/20 p-8 text-center text-white/60">
        {labels.empty}
      </p>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {stations.map((s) => (
        <StationCard
          key={s.id}
          station={s}
          genresBySlug={genresBySlug}
          labels={{ curated: labels.curated, location: labels.location }}
        />
      ))}
    </div>
  );
}
