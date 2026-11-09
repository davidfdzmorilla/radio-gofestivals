import { sitemapIndexResponse } from '@/lib/sitemap-index-response';

export const dynamic = 'force-dynamic';

/**
 * La misma URL que se declara en robots.txt. Search Console cachea el fallo de una URL de sitemap
 * que no pudo leer y no la reintenta, así que el índice se sirve también aquí (ya pasó con
 * /sitemap.xml, que sigue respondiendo igual).
 */
export const GET = sitemapIndexResponse;
