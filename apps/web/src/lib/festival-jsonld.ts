import {
  festivalDescription,
  festivalImageSrc,
  festivalLocation,
  festivalPath,
  safeHttpUrl,
  type Festival,
} from '@/lib/festivals';
import { SITE_URL } from '@/lib/site';

const DESCRIPTION_MAX = 500;

/** Las fechas de la API son medianoche UTC de un día natural: se emiten como fecha ISO sin hora (sin zona que correr). */
function isoDay(value: string | null): string | null {
  if (!value) return null;
  const t = Date.parse(value);
  return Number.isNaN(t) ? null : new Date(t).toISOString().slice(0, 10);
}

/**
 * JSON-LD `Event` de un festival (rich result de Google: fechas y lugar en el snippet).
 * Devuelve null si faltan datos obligatorios (fecha de inicio válida o lugar) — mejor
 * sin marcado que con un marcado que Google marque como erróneo.
 * `image` solo si la URL pasa `festivalImageSrc` (hosts de gofestivals). Sin `offers`:
 * la API no trae entradas ni precios.
 */
export function festivalEventLd(
  festival: Festival,
  locale: string,
): Record<string, unknown> | null {
  const startDate = isoDay(festival.startDate);
  const place = festivalLocation(festival, locale)?.trim();
  if (!startDate || !place) return null;

  const endDate = isoDay(festival.endDate);
  const description = festivalDescription(festival, locale)?.trim();
  const website = safeHttpUrl(festival.website);
  const image = festivalImageSrc(festival);

  return {
    '@context': 'https://schema.org',
    '@type': 'Event',
    name: festival.name,
    startDate,
    ...(endDate && endDate >= startDate ? { endDate } : {}),
    eventStatus: 'https://schema.org/EventScheduled',
    eventAttendanceMode: 'https://schema.org/OfflineEventAttendanceMode',
    location: {
      '@type': 'Place',
      name: place,
      address: festival.countryCode
        ? { '@type': 'PostalAddress', addressCountry: festival.countryCode }
        : place,
    },
    url: `${SITE_URL}/${locale}${festivalPath(festival)}`,
    ...(image ? { image: [image] } : {}),
    ...(description ? { description: description.slice(0, DESCRIPTION_MAX) } : {}),
    ...(website ? { sameAs: website } : {}),
  };
}
