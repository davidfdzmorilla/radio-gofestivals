import { TrackedAnchor } from '@/components/analytics/TrackedAnchor';
import { FestivalImage } from '@/components/festivals/FestivalImage';
import { Badge } from '@/components/ui/badge';
import {
  festivalDescription,
  festivalImageSrc,
  festivalLocation,
  festivalUrl,
  formatFestivalDates,
  safeHttpUrl,
  type Festival,
} from '@/lib/festivals';
import { initials } from '@/lib/utils';

const DESCRIPTION_MAX = 400;

interface Props {
  festival: Festival;
  locale: string;
  color: string;
  /** "Empieza dentro de 5 semanas" / "Ocurre ahora" / "Esta edición ya terminó". */
  phaseLabel: string;
  phase: 'upcoming' | 'ongoing' | 'ended';
  countryName: string | null;
  labels: { viewOnGofestivals: string; officialSite: string };
}

function clamp(text: string): string {
  return text.length <= DESCRIPTION_MAX ? text : `${text.slice(0, DESCRIPTION_MAX).trimEnd()}…`;
}

export function FestivalHero({ festival, locale, color, phaseLabel, phase, countryName, labels }: Props) {
  const description = festivalDescription(festival, locale);
  const website = safeHttpUrl(festival.website);
  const place = festivalLocation(festival, locale);
  // El texto del lugar ya suele incluir el país ("Brest, Bretaña, Francia"): solo se añade si falta.
  const where = [place, countryName && !place?.includes(countryName) ? countryName : null]
    .filter(Boolean)
    .join(' · ');
  return (
    <section className="flex flex-col gap-8 sm:flex-row sm:items-start">
      <FestivalImage
        src={festivalImageSrc(festival)}
        alt={festival.name}
        fallbackText={initials(festival.name)}
        fallbackColor={color}
        priority
      />
      <div className="min-w-0 flex-1 space-y-4">
        <Badge tone={phase === 'ended' ? 'neutral' : 'cyan'}>{phaseLabel}</Badge>
        <h1 className="font-display text-[clamp(2rem,6vw,3.5rem)] font-semibold leading-[1.05] text-fg-0">
          {festival.name}
        </h1>
        <p className="font-mono text-sm uppercase tracking-wide text-cyan">
          {formatFestivalDates(locale, festival.startDate, festival.endDate)}
        </p>
        {where && <p className="text-fg-1">{where}</p>}
        {description && <p className="max-w-prose text-sm leading-relaxed text-fg-2">{clamp(description)}</p>}
        <div className="flex flex-wrap items-center gap-3 pt-1">
          <TrackedAnchor
            event={{ festival_id: festival.id, destination: 'gofestivals', placement: 'hero' }}
            href={festivalUrl(locale, festival)}
            className="inline-flex min-h-11 items-center rounded-full bg-magenta px-5 py-2 text-sm font-semibold text-bg-0 transition-opacity hover:opacity-90"
          >
            {labels.viewOnGofestivals}
          </TrackedAnchor>
          {website && (
            <TrackedAnchor
              event={{ festival_id: festival.id, destination: 'official', placement: 'hero' }}
              href={website}
              rel="nofollow noopener noreferrer"
              className="inline-flex min-h-11 items-center rounded-full border border-fg-3 px-5 py-2 text-sm font-medium text-fg-1 transition-colors hover:border-fg-2 hover:text-fg-0"
            >
              {labels.officialSite}
            </TrackedAnchor>
          )}
        </div>
      </div>
    </section>
  );
}
