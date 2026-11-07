import { FestivalImage } from '@/components/festivals/FestivalImage';
import { Link } from '@/i18n/navigation';
import { initials } from '@/lib/utils';
import {
  festivalImageSrc,
  festivalLocation,
  festivalPath,
  formatFestivalDates,
  type Festival,
} from '@/lib/festivals';

const DEFAULT_COLOR = '#8B4EE8';

interface Props {
  festivals: Festival[];
  locale: string;
  /** Color de respaldo cuando el festival no tiene imagen (el del género de la página). */
  color?: string;
}

/** Lista de tarjetas de festival; cada una lleva a su ficha en la radio. */
export function FestivalCards({ festivals, locale, color = DEFAULT_COLOR }: Props) {
  return (
    <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {festivals.map((f) => {
        const place = festivalLocation(f, locale);
        return (
          <li key={f.id}>
            <Link
              href={festivalPath(f)}
              className="flex h-full items-center gap-3 rounded-xl border border-fg-3/50 bg-bg-2 p-3 transition-colors hover:border-fg-3 hover:bg-bg-3"
            >
              <FestivalImage
                src={festivalImageSrc(f)}
                alt={f.name}
                fallbackText={initials(f.name)}
                fallbackColor={color}
                variant="card"
                decorative
              />
              <span className="flex min-w-0 flex-1 flex-col gap-1">
                <span className="font-mono text-[12px] uppercase tracking-widest text-cyan">
                  {formatFestivalDates(locale, f.startDate, f.endDate)}
                </span>
                <span className="line-clamp-2 font-display text-[15px] font-semibold leading-snug text-fg-0">
                  {f.name}
                </span>
                {place && <span className="truncate text-sm text-fg-2">{place}</span>}
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
