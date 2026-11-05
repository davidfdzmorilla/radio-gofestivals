import { Link } from '@/i18n/navigation';
import {
  festivalLocation,
  festivalPath,
  formatFestivalDates,
  type Festival,
} from '@/lib/festivals';

interface Props {
  festivals: Festival[];
  locale: string;
  labels: { title: string; viewAll: string; source: string };
}

/**
 * Próximos festivales de un género (datos de gofestivals). Presentacional:
 * recibe los festivales ya cargados y no pinta nada si no hay ninguno.
 * Cada tarjeta lleva a la ficha del festival en la radio (enlazado interno); el
 * calendario completo está en gofestivals (mismo propietario, sin nofollow).
 */
export function UpcomingFestivals({ festivals, locale, labels }: Props) {
  if (festivals.length === 0) return null;
  return (
    <section aria-labelledby="upcoming-festivals-title" className="space-y-4">
      <div className="flex items-baseline justify-between gap-4">
        <h2
          id="upcoming-festivals-title"
          className="font-display text-xl font-semibold text-fg-0"
        >
          {labels.title}
        </h2>
        <Link
          href="/festivals"
          className="-my-2 shrink-0 py-2 font-mono text-[12px] uppercase tracking-widest text-fg-2 transition-colors hover:text-fg-0"
        >
          {labels.viewAll}
        </Link>
      </div>
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {festivals.map((f) => (
          <li key={f.id}>
            <Link
              href={festivalPath(f)}
              className="flex h-full flex-col gap-1 rounded-xl border border-fg-3/50 bg-bg-2 p-4 transition-colors hover:border-fg-3 hover:bg-bg-3"
            >
              <span className="font-mono text-[12px] uppercase tracking-widest text-cyan">
                {formatFestivalDates(locale, f.startDate, f.endDate)}
              </span>
              <span className="line-clamp-2 font-display text-[15px] font-semibold leading-snug text-fg-0">
                {f.name}
              </span>
              {festivalLocation(f, locale) && (
                <span className="truncate text-sm text-fg-2">{festivalLocation(f, locale)}</span>
              )}
            </Link>
          </li>
        ))}
      </ul>
      <p className="text-xs text-fg-2">{labels.source}</p>
    </section>
  );
}
