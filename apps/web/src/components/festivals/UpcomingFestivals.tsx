import { FestivalCards } from '@/components/festivals/FestivalCards';
import { Link } from '@/i18n/navigation';
import type { Festival } from '@/lib/festivals';

interface Props {
  festivals: Festival[];
  locale: string;
  labels: { title: string; viewAll: string; source: string };
  /** Color del género de la página, para el recuadro de las tarjetas sin imagen. */
  color?: string;
}

/**
 * Próximos festivales de un género (datos de gofestivals). Presentacional:
 * recibe los festivales ya cargados y no pinta nada si no hay ninguno. Cada
 * tarjeta lleva a la ficha del festival en la radio (enlazado interno).
 */
export function UpcomingFestivals({ festivals, locale, labels, color }: Props) {
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
      <FestivalCards festivals={festivals} locale={locale} color={color} />
      <p className="text-xs text-fg-2">{labels.source}</p>
    </section>
  );
}
