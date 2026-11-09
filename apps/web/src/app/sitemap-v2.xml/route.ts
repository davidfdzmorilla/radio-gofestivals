import { SITE_URL } from '@/lib/site';

// URL antigua que se envió a Search Console. Redirección permanente al índice (ADR 015): 301
// en vez de 410 para que los reintentos de Google acaben en el sitemap nuevo, no en un error.
// Destino absoluto: detrás de Traefik `request.url` es el host interno del contenedor.
export function GET(): Response {
  return Response.redirect(`${SITE_URL}/sitemap.xml`, 301);
}
