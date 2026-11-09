import { sitemapIndexResponse } from '@/lib/sitemap-index-response';

// Sin prerender en build: necesita la API viva (el CI no la tiene). La caché la gobierna el
// Cache-Control de la respuesta.
export const dynamic = 'force-dynamic';

/** Índice de sitemaps (ADR 015). Mismo contenido que /sitemap-index.xml, sin redirección. */
export const GET = sitemapIndexResponse;
