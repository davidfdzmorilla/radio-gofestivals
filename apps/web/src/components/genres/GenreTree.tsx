import { Link } from '@/i18n/navigation';
import { cn } from '@/lib/utils';
import type { Genre } from '@/lib/types';

interface Props {
  genres: Genre[];
  countLabel: (count: number) => string;
  moreLabel: string;
}

/** Por debajo de este nº de emisoras un género pasa a la fila de píldoras "Más géneros". */
export const MAIN_GENRE_MIN_STATIONS = 20;
/** Subgéneros nombrados en la tarjeta; el resto se resume en "+N". */
const SUBGENRES_SHOWN = 2;

const hoverRotations = [
  'hover:-rotate-0.5',
  'hover:rotate-0.5',
  'hover:-rotate-1',
  'hover:rotate-1',
];

/** Una línea de texto con los subgéneros con emisoras: "Deep House · Tech House · +2". */
export function subgenreSummary(genre: Genre): string {
  const subs = genre.children.filter((c) => c.station_count > 0);
  if (subs.length === 0) return '';
  const names = subs.slice(0, SUBGENRES_SHOWN).map((c) => c.name);
  const rest = subs.length - names.length;
  return [...names, ...(rest > 0 ? [`+${rest}`] : [])].join(' · ');
}

export function GenreTree({ genres, countLabel, moreLabel }: Props) {
  // Sin emisoras no hay nada que explorar; el resto, de más a menos emisoras.
  const roots = genres
    .filter((g) => g.parent_id === null && g.station_count > 0)
    .sort((a, b) => b.station_count - a.station_count || a.name.localeCompare(b.name));
  const main = roots.filter((g) => g.station_count >= MAIN_GENRE_MIN_STATIONS);
  const more = roots.filter((g) => g.station_count < MAIN_GENRE_MIN_STATIONS);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {main.map((g, i) => {
          const summary = subgenreSummary(g);
          return (
            <Link
              key={g.slug}
              href={`/genres/${g.slug}`}
              className={cn(
                'group relative flex min-h-[104px] flex-col justify-between overflow-hidden rounded-xl border border-fg-3 bg-bg-2 p-4 transition-all duration-200',
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
                <p className="font-display text-lg font-semibold leading-tight text-fg-0">
                  {g.name}
                </p>
                <p className="mt-1 font-mono text-[12px] uppercase tracking-wide text-fg-2">
                  {countLabel(g.station_count)}
                </p>
              </div>
              <p className="mt-2 line-clamp-2 min-h-8 pl-3 sm:line-clamp-1 sm:min-h-4 font-mono text-[11px] uppercase tracking-wide text-fg-2">
                {summary}
              </p>
            </Link>
          );
        })}
      </div>

      {more.length > 0 && (
        <nav aria-label={moreLabel} className="space-y-2">
          <p className="font-mono text-[12px] uppercase tracking-widest text-fg-2">
            {moreLabel}
          </p>
          <ul className="flex flex-wrap gap-2">
            {more.map((g) => (
              <li key={g.slug}>
                <Link
                  href={`/genres/${g.slug}`}
                  className="inline-flex items-center gap-2 rounded-full border border-fg-3 px-3 py-1.5 font-mono text-[12px] uppercase tracking-wide text-fg-1 transition-colors hover:border-fg-2 hover:text-fg-0"
                >
                  <span
                    aria-hidden
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ backgroundColor: g.color_hex }}
                  />
                  {g.name} · {g.station_count}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      )}
    </div>
  );
}
