import { getSitemapGroups } from './sitemap-data';
import { latestModified, renderSitemapIndex, SITEMAP_CHILDREN, XML_HEADERS } from './sitemap-xml';

/** Respuesta del índice de sitemaps; la sirven /sitemap.xml y /sitemap-index.xml con el mismo contenido. */
export async function sitemapIndexResponse(): Promise<Response> {
  const groups = await getSitemapGroups();
  const body = renderSitemapIndex(
    SITEMAP_CHILDREN.map(({ group, path }) => ({
      path,
      lastModified: latestModified(groups[group]),
    })),
  );
  return new Response(body, { headers: XML_HEADERS });
}
