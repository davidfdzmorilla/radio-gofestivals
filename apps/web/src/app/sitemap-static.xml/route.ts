import { getSitemapGroups } from '@/lib/sitemap-data';
import { renderUrlset, XML_HEADERS } from '@/lib/sitemap-xml';

export const dynamic = 'force-dynamic';

export async function GET(): Promise<Response> {
  const groups = await getSitemapGroups();
  return new Response(renderUrlset(groups.static), { headers: XML_HEADERS });
}
