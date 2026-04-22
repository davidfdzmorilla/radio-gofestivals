import { Link } from '@/i18n/navigation';
import type { Genre } from '@/lib/types';

interface Props {
  genres: Genre[];
  countLabel: (count: number) => string;
}

export function GenreTree({ genres, countLabel }: Props) {
  const roots = genres.filter((g) => g.parent_id === null);
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
      {roots.map((g) => (
        <Link
          key={g.slug}
          href={`/genres/${g.slug}`}
          className="group rounded-lg border border-white/10 bg-white/5 p-4 transition-all hover:scale-[1.02] hover:border-white/30"
          style={{
            borderLeftColor: g.color_hex,
            borderLeftWidth: '4px',
          }}
        >
          <p className="font-display text-lg font-semibold text-white group-hover:text-white">
            {g.name}
          </p>
          <p className="mt-1 text-xs text-white/50">
            {countLabel(g.station_count)}
          </p>
        </Link>
      ))}
    </div>
  );
}
