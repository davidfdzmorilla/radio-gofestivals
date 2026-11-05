const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export type LogoSize = 'sm' | 'lg';

/**
 * URL del logo ya procesado de una emisora (ADR 011). Lleva `v=<hash>`: el API
 * responde con caché inmutable de un año cuando coincide con el hash actual, y un
 * logo nuevo cambia la URL, así que nunca se ve uno desfasado.
 */
export function stationLogoUrl(slug: string, hash: string, size: LogoSize): string {
  const query = new URLSearchParams({ size, v: hash });
  return `${BASE}/api/v1/stations/${encodeURIComponent(slug)}/logo?${query.toString()}`;
}
