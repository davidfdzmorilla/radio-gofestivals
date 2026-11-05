import { festivalCalendarUrl, festivalUrl, formatFestivalDates, type Festival } from '@/lib/festivals';

interface Props {
  festivals: Festival[];
  locale: string;
  labels: { title: string; viewAll: string; source: string };
}

/**
 * Próximos festivales de un género (datos de gofestivals). Presentacional:
 * recibe los festivales ya cargados y no pinta nada si no hay ninguno.
 * Enlaces normales (mismo propietario, valor contextual): sin nofollow.
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
        <a
          href={festivalCalendarUrl(locale)}
          className="-my-2 shrink-0 py-2 font-mono text-[12px] uppercase tracking-widest text-fg-2 transition-colors hover:text-fg-0"
        >
          {labels.viewAll}
        </a>
      </div>
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {festivals.map((f) => (
          <li key={f.id}>
            <a
              href={festivalUrl(locale, f)}
              className="flex h-full flex-col gap-1 rounded-xl border border-fg-3/50 bg-bg-2 p-4 transition-colors hover:border-fg-3 hover:bg-bg-3"
            >
              <span className="font-mono text-[12px] uppercase tracking-widest text-cyan">
                {formatFestivalDates(locale, f.startDate, f.endDate)}
              </span>
              <span className="line-clamp-2 font-display text-[15px] font-semibold leading-snug text-fg-0">
                {f.name}
              </span>
              {f.location && (
                <span className="truncate text-sm text-fg-2">{f.location}</span>
              )}
            </a>
          </li>
        ))}
      </ul>
      <p className="text-xs text-fg-2">{labels.source}</p>
    </section>
  );
}
