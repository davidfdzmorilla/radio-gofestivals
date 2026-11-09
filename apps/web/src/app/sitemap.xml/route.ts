import { getSitemapGroups } from '@/lib/sitemap-data';
import { latestModified, renderSitemapIndex, SITEMAP_CHILDREN, XML_HEADERS } from '@/lib/sitemap-xml';

// Sin prerender en build: necesita la API viva (el CI no la tiene). La caché la gobierna el
// Cache-Control de la respuesta.
export const dynamic = 'force-dynamic';

/** Índice de sitemaps (ADR 015). `/sitemap-v2.xml` redirige aquí. */
export async function GET(): Promise<Response> {
  const groups = await getSitemapGroups();
  const body = renderSitemapIndex(
    SITEMAP_CHILDREN.map(({ group, path }) => ({
      path,
      lastModified: latestModified(groups[group]),
    })),
  );
  return new Response(body, { headers: XML_HEADERS });
}
