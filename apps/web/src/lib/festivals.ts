import { apiFetch, ApiError } from '@/lib/api';
import { FestivalSchema, type Festival } from '@/lib/types';

// Festivales de gofestivals (proyecto hermano, ADR 009). Se consume su API HTTP
// pública, no su base de datos. Los listados son fail-soft (si la API falla, no
// se muestran); el detalle propaga los fallos para no cachear un 404 falso.

// Cadena vacía (p. ej. copiada de .env.example) cuenta como no definida.
const API_BASE =
  (process.env.GOFESTIVALS_API_URL ?? '').trim().replace(/\/+$/, '') || 'https://api.gofestivals.es';
const TIMEOUT_MS = 3000;
const REVALIDATE_S = 3600;
const DAY_MS = 86_400_000;

export type { Festival };

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

// Debe coincidir con `images.remotePatterns` de next.config.mjs: next/image LANZA
// en el render si recibe un host no configurado, así que solo se admite este.
const IMAGE_HOST = 'proyecto-images-gofestivals.s3.eu-west-3.amazonaws.com';
const IMAGE_PATH_PREFIX = '/festivals/';

/** URL de imagen apta para next/image (https, bucket de gofestivals, ruta de festivales) o null. */
export function festivalImageSrc(festival: Pick<Festival, 'imageUrl'>): string | null {
  if (!festival.imageUrl) return null;
  try {
    const u = new URL(festival.imageUrl);
    const ok = u.protocol === 'https:' && u.hostname === IMAGE_HOST && u.pathname.startsWith(IMAGE_PATH_PREFIX);
    return ok ? u.toString() : null;
  } catch {
    return null;
  }
}

/** Solo http(s): la web oficial viene de una base de datos ajena y acaba en un href (un `javascript:` sería XSS). */
export function safeHttpUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const u = new URL(value.trim());
    return u.protocol === 'https:' || u.protocol === 'http:' ? u.toString() : null;
  } catch {
    return null;
  }
}

export function festivalUrl(locale: string, festival: Pick<Festival, 'id' | 'name'>): string {
  return `${siteFor(locale)}/festival/${festival.id}/${festivalSlug(festival.name) || 'festival'}`;
}

export function festivalCalendarUrl(locale: string): string {
  return `${siteFor(locale)}/calendar`;
}

/** Ruta interna de la ficha de la radio (sin prefijo de idioma: la añade el Link/redirect de next-intl). */
export function festivalPath(festival: Pick<Festival, 'id' | 'name'>): string {
  return `/festivals/${festival.id}/${festivalSlug(festival.name) || 'festival'}`;
}

export function festivalLocation(
  festival: Pick<Festival, 'location' | 'locationEn'>,
  locale: string,
): string | null {
  return (locale === 'en' ? (festival.locationEn ?? festival.location) : festival.location) ?? null;
}

export function festivalDescription(
  festival: Pick<Festival, 'description' | 'descriptionEn'>,
  locale: string,
): string | null {
  return (locale === 'en' ? (festival.descriptionEn ?? festival.description) : festival.description) ?? null;
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

export type FestivalPhase = 'upcoming' | 'ongoing' | 'ended';

/** end_date es el último día a las 00:00Z: el festival sigue en curso durante todo ese día. */
export function festivalPhase(
  festival: Pick<Festival, 'startDate' | 'endDate'>,
  now: Date = new Date(),
): FestivalPhase {
  const start = Date.parse(festival.startDate);
  const endRaw = festival.endDate ? Date.parse(festival.endDate) : start;
  const end = (Number.isNaN(endRaw) ? start : endRaw) + DAY_MS;
  if (now.getTime() >= end) return 'ended';
  return now.getTime() >= start ? 'ongoing' : 'upcoming';
}

async function fetchRaw(path: string): Promise<unknown> {
  return apiFetch<unknown>(path, {
    baseUrl: API_BASE,
    timeoutMs: TIMEOUT_MS,
    revalidate: REVALIDATE_S,
  });
}

function parseFestivals(raw: unknown): Festival[] {
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((item): Festival[] => {
    const parsed = FestivalSchema.safeParse(item);
    return parsed.success && !Number.isNaN(Date.parse(parsed.data.startDate)) ? [parsed.data] : [];
  });
}

interface ListOptions {
  genre?: string;
  limit?: number;
  now?: Date;
}

/** Próximos festivales (fail-soft: ante cualquier fallo, lista vacía), ordenados por fecha. */
export async function getUpcomingFestivals({
  genre,
  limit = 4,
  now = new Date(),
}: ListOptions = {}): Promise<Festival[]> {
  const params = new URLSearchParams({ upcoming: 'true' });
  if (genre) params.set('genre', genre);
  // Margen sobre `limit`: se re-filtra y re-ordena aquí por si la API devolviera algo pasado.
  params.set('limit', String(Math.min(limit * 2, 100)));
  let raw: unknown;
  try {
    raw = await fetchRaw(`/api/festivals?${params.toString()}`);
  } catch {
    return [];
  }
  return parseFestivals(raw)
    .filter((f) => festivalPhase(f, now) !== 'ended')
    .sort((a, b) => Date.parse(a.startDate) - Date.parse(b.startDate))
    .slice(0, limit);
}

/** Todos los próximos (100, el tope de la API): índice, sitemap y rutas estáticas. */
export function getAllUpcomingFestivals(now: Date = new Date()): Promise<Festival[]> {
  return getUpcomingFestivals({ limit: 100, now });
}

/**
 * Detalle de un festival. `null` solo si no existe (id no numérico o 404): la
 * API devuelve 500 para ids no numéricos, así que se descartan antes de llamar.
 * Cualquier otro fallo (red, 5xx, JSON raro) se PROPAGA: la página no debe
 * convertir una caída de la API en un 404 cacheado.
 */
export async function getFestival(id: string): Promise<Festival | null> {
  if (!/^\d{1,9}$/.test(id)) return null;
  let raw: unknown;
  try {
    raw = await fetchRaw(`/api/festivals/${id}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
  const parsed = FestivalSchema.safeParse(raw);
  if (!parsed.success) throw new Error(`Festival ${id}: payload inválido`);
  return parsed.data;
}
