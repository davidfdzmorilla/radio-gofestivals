import { z } from 'zod';

// Festivales de gofestivals (proyecto hermano). Se consume su API HTTP pública
// (Fase D de RADIO-CROSSLINKS-PLAN.md en ese repo), no su base de datos.
// Fail-soft: si la API falla o tarda, el módulo simplemente no se muestra.

// Cadena vacía (p. ej. copiada de .env.example) cuenta como no definida.
const API_BASE =
  (process.env.GOFESTIVALS_API_URL ?? '').trim().replace(/\/+$/, '') || 'https://api.gofestivals.es';
const TIMEOUT_MS = 3000;
const REVALIDATE_S = 3600;
const DAY_MS = 86_400_000;

const FestivalSchema = z.object({
  id: z.union([z.number(), z.string()]).transform(String),
  name: z.string().min(1),
  start_date: z.string(),
  end_date: z.string().nullish(),
  location: z.string().nullish(),
  location_en: z.string().nullish(),
});

export interface Festival {
  id: string;
  name: string;
  startDate: string;
  endDate: string | null;
  location: string | null;
}

type FestivalLocale = 'es' | 'en';

const SITES: Record<FestivalLocale, string> = {
  es: 'https://gofestivals.es/es',
  en: 'https://gofestivals.eu/en',
};

function siteFor(locale: string): string {
  return SITES[locale === 'es' ? 'es' : 'en'];
}

/** Idéntico a `generateSlug` de gofestivals (utils/festivalUtils.js): sin slug, su ficha redirige y pierde el idioma. */
export function festivalSlug(name: string): string {
  return name
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

export function festivalUrl(locale: string, festival: Pick<Festival, 'id' | 'name'>): string {
  return `${siteFor(locale)}/festival/${festival.id}/${festivalSlug(festival.name) || 'festival'}`;
}

export function festivalCalendarUrl(locale: string): string {
  return `${siteFor(locale)}/calendar`;
}

/** Las fechas de la API son medianoche UTC de un día natural: se formatean en UTC para no correrlas un día. */
export function formatFestivalDates(
  locale: string,
  startDate: string,
  endDate: string | null,
): string {
  const fmt = new Intl.DateTimeFormat(locale, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  });
  const start = new Date(startDate);
  if (Number.isNaN(start.getTime())) return '';
  const end = endDate ? new Date(endDate) : null;
  if (!end || Number.isNaN(end.getTime()) || end.getTime() === start.getTime()) {
    return fmt.format(start);
  }
  return fmt.formatRange(start, end);
}

function localizedLocation(locale: string, f: z.infer<typeof FestivalSchema>): string | null {
  return (locale === 'en' ? (f.location_en ?? f.location) : f.location) ?? null;
}

interface Options {
  genre: string;
  locale: string;
  limit?: number;
  now?: Date;
}

export async function getUpcomingFestivals({
  genre,
  locale,
  limit = 4,
  now = new Date(),
}: Options): Promise<Festival[]> {
  const params = new URLSearchParams({
    genre,
    upcoming: 'true',
    // Margen sobre `limit`: se re-filtra y re-ordena aquí por si la API devolviera algo pasado.
    limit: String(limit * 2),
  });
  let raw: unknown;
  try {
    const res = await fetch(`${API_BASE}/api/festivals?${params.toString()}`, {
      headers: { Accept: 'application/json' },
      signal: AbortSignal.timeout(TIMEOUT_MS),
      next: { revalidate: REVALIDATE_S },
    });
    if (!res.ok) return [];
    raw = await res.json();
  } catch {
    return [];
  }
  if (!Array.isArray(raw)) return [];

  const today = now.getTime();
  return raw
    .flatMap((item): Festival[] => {
      const parsed = FestivalSchema.safeParse(item);
      if (!parsed.success) return [];
      const f = parsed.data;
      const start = Date.parse(f.start_date);
      if (Number.isNaN(start)) return [];
      const end = f.end_date ? Date.parse(f.end_date) : start;
      // end_date es el último día a las 00:00Z: sigue en curso durante todo ese día.
      if ((Number.isNaN(end) ? start : end) + DAY_MS <= today) return [];
      return [
        {
          id: f.id,
          name: f.name,
          startDate: f.start_date,
          endDate: f.end_date ?? null,
          location: localizedLocation(locale, f),
        },
      ];
    })
    .sort((a, b) => Date.parse(a.startDate) - Date.parse(b.startDate))
    .slice(0, limit);
}
