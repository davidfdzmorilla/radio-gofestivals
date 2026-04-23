import { Link } from '@/i18n/navigation';
import { cn } from '@/lib/utils';
import type { Genre } from '@/lib/types';

interface Props {
  genres: Genre[];
  countLabel: (count: number) => string;
}

const hoverRotations = [
  'hover:-rotate-0.5',
  'hover:rotate-0.5',
  'hover:-rotate-1',
  'hover:rotate-1',
];

export function GenreTree({ genres, countLabel }: Props) {
  const roots = genres.filter((g) => g.parent_id === null);
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {roots.map((g, i) => (
        <Link
          key={g.slug}
          href={`/genres/${g.slug}`}
          className={cn(
            'group relative overflow-hidden rounded-xl border border-fg-3 bg-bg-2 p-4 transition-all duration-200',
            'hover:-translate-y-0.5 hover:border-fg-2 hover:bg-bg-3',
            hoverRotations[i % hoverRotations.length],
          )}
        >
          <span
            aria-hidden
            className="absolute inset-y-0 left-0 w-1.5 transition-all duration-200 group-hover:w-2.5"
            style={{ backgroundColor: g.color_hex }}
          />
          <div className="pl-3">
            <p className="font-display text-lg font-semibold text-fg-0">
              {g.name}
            </p>
            <p className="mt-1 font-mono text-[11px] uppercase tracking-wide text-fg-2">
              {countLabel(g.station_count)}
            </p>
          </div>
        </Link>
      ))}
    </div>
  );
}
