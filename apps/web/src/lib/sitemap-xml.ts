import { SITE_URL } from './site';
import type { SitemapEntry, SitemapGroup } from './sitemap-data';

const esc = (v: string): string =>
  v.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&apos;');

/** Límites del protocolo sitemaps.org. */
export const SITEMAP_MAX_URLS = 50_000;

export const SITEMAP_CHILDREN: ReadonlyArray<{ group: SitemapGroup; path: string }> = [
  { group: 'static', path: '/sitemap-static.xml' },
  { group: 'genres', path: '/sitemap-genres.xml' },
  { group: 'countries', path: '/sitemap-countries.xml' },
  { group: 'stations', path: '/sitemap-stations.xml' },
];

/** `<urlset>` con hreflang y lastmod real. Sin changefreq ni priority (Google los ignora). */
export function renderUrlset(entries: SitemapEntry[]): string {
  if (entries.length > SITEMAP_MAX_URLS) throw new Error('sitemap exceeds 50,000 URLs');
  const urls = entries.map((e) => {
    const lines = ['  <url>', `    <loc>${esc(e.url)}</loc>`];
    for (const [lang, href] of Object.entries(e.alternates)) {
      lines.push(`    <xhtml:link rel="alternate" hreflang="${esc(lang)}" href="${esc(href)}" />`);
    }
    if (e.lastModified) lines.push(`    <lastmod>${esc(e.lastModified)}</lastmod>`);
    lines.push('  </url>');
    return lines.join('\n');
  });
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ...urls,
    '</urlset>',
    '',
  ].join('\n');
}

export function renderSitemapIndex(children: Array<{ path: string; lastModified?: string }>): string {
  const items = children.map((c) =>
    [
      '  <sitemap>',
      `    <loc>${esc(`${SITE_URL}${c.path}`)}</loc>`,
      ...(c.lastModified ? [`    <lastmod>${esc(c.lastModified)}</lastmod>`] : []),
      '  </sitemap>',
    ].join('\n'),
  );
  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ...items,
    '</sitemapindex>',
    '',
  ].join('\n');
}

export const XML_HEADERS = {
  'Content-Type': 'application/xml; charset=utf-8',
  'Cache-Control': 'public, max-age=3600, s-maxage=3600, stale-while-revalidate=86400',
} as const;
