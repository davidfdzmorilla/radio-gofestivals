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
      {roots.map((g, i) => {
        // Solo subgéneros con emisoras: una página vacía no aporta nada al visitante.
        const children = g.children.filter((c) => c.station_count > 0);
        return (
          <div
            key={g.slug}
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
              <Link
                href={`/genres/${g.slug}`}
                className="block after:absolute after:inset-0 after:content-['']"
              >
                <p className="font-display text-lg font-semibold text-fg-0">
                  {g.name}
                </p>
                <p className="mt-1 font-mono text-[12px] uppercase tracking-wide text-fg-2">
                  {countLabel(g.station_count)}
                </p>
              </Link>
              {children.length > 0 && (
                <ul className="relative z-10 mt-3 flex flex-wrap gap-1.5">
                  {children.map((c) => (
                    <li key={c.slug}>
                      <Link
                        href={`/genres/${c.slug}`}
                        className="inline-block rounded-full border border-fg-3 px-2.5 py-1 font-mono text-[11px] uppercase tracking-wide text-fg-1 transition-colors hover:border-fg-2 hover:text-fg-0"
                      >
                        {c.name}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
