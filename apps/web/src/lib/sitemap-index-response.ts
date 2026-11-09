import { renderSitemapIndex, SITEMAP_CHILDREN, XML_HEADERS } from './sitemap-xml';

/**
 * Respuesta del índice de sitemaps; la sirven /sitemap.xml y /sitemap-index.xml con el mismo
 * contenido. Es estático (no consulta la API) y sin `lastmod`: cualquier fecha agregada sería
 * inventada.
 */
export function sitemapIndexResponse(): Response {
  return new Response(renderSitemapIndex(SITEMAP_CHILDREN.map(({ path }) => ({ path }))), {
    headers: XML_HEADERS,
  });
}
