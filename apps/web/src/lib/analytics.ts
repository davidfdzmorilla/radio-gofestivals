/**
 * Google Analytics 4 (ADR 013). El ID de medición es público (va en cada página), pero se
 * configura por entorno: sin `NEXT_PUBLIC_GA_MEASUREMENT_ID` válido no se carga nada.
 */

/** Evento que dispara el banner de consentimiento al elegir, para cargar GA sin recargar. */
export const CONSENT_CHANGED_EVENT = 'rgf:consent-changed';

const MEASUREMENT_ID = /^G-[A-Z0-9]{6,14}$/;

/** Devuelve el ID si tiene forma de ID de medición de GA4; si no, null (analítica desactivada). */
export function validGaId(raw: string | null | undefined): string | null {
  const id = raw?.trim();
  return id && MEASUREMENT_ID.test(id) ? id : null;
}

export const GA_MEASUREMENT_ID = validGaId(process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID);

/**
 * Eventos personalizados (ADR 014). Unión cerrada: un nombre o un parámetro mal escrito no
 * compila. Nunca llevan datos personales: ni texto libre del usuario ni identificadores de cuenta.
 */
export interface StationEventParams {
  station_slug: string;
  genre?: string;
  country?: string;
  /** Superficie desde la que se reproduce (ver `pageSource`). */
  source: string;
}

export interface AnalyticsEvents {
  play_start: StationEventParams;
  play_30s: StationEventParams;
  play_error: StationEventParams;
  festival_outbound: {
    festival_id: string;
    destination: 'gofestivals' | 'official';
    placement: 'hero';
  };
  favorite_add: { station_slug: string; logged_in: boolean };
}

type GtagFn = (command: 'event', name: string, params: Record<string, unknown>) => void;

/**
 * Envía un evento a GA4. No hace nada si GA no está cargado (sin consentimiento, sin ID, o aún
 * arrancando): el consentimiento se aplica una sola vez, al cargar el script. Nunca lanza.
 */
export function trackEvent<K extends keyof AnalyticsEvents>(name: K, params: AnalyticsEvents[K]): void {
  if (typeof window === 'undefined') return;
  try {
    const gtag = (window as unknown as { gtag?: GtagFn }).gtag;
    if (typeof gtag === 'function') gtag('event', name, { ...params });
  } catch {
    // La analítica jamás debe romper la escucha.
  }
}

/** Sección de la web en la que está el usuario, para saber qué superficies empujan escucha. */
export function pageSource(pathname: string): string {
  const parts = pathname.split('/').filter(Boolean);
  // El primer segmento es el idioma (es/en).
  const section = parts[1];
  if (!section) return 'home';
  const known: Record<string, string> = {
    genres: 'genre',
    countries: 'country',
    stations: 'station',
    festivals: 'festival',
    search: 'search',
    trending: 'trending',
    favorites: 'favorites',
    new: 'new',
  };
  return known[section] ?? 'other';
}

/** Parámetros comunes de un evento de emisora, a partir de la emisora y la página actual. */
export function stationEventParams(
  station: { slug: string; genres: string[]; country_code: string | null },
  pathname: string = typeof window === 'undefined' ? '/' : window.location.pathname,
): StationEventParams {
  const params: StationEventParams = { station_slug: station.slug, source: pageSource(pathname) };
  // Minúsculas siempre: GA distingue 'DE' de 'de' y partiría los informes en dos.
  if (station.genres[0]) params.genre = station.genres[0].toLowerCase();
  if (station.country_code) params.country = station.country_code.toLowerCase();
  return params;
}
