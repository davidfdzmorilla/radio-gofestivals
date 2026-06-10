import { buildSitemapEntries } from '@/lib/sitemap-data';

// force-dynamic: este handler existe para servir una URL SIEMPRE fresca a
// GSC; prerenderizarlo en build además exige la API viva durante `next
// build` (rompía el CI, donde no hay backend). La caché la gobierna el
// Cache-Control de la respuesta.
export const dynamic = 'force-dynamic';

function xmlEscape(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

/**
 * Sitemap served from a plain Route Handler at a URL Google Search Console
 * has never seen — `/sitemap.xml` had its fetch result cached as a failure
 * by GSC during a deploy window, and GSC will not retry that exact URL.
 * The native `app/sitemap.ts` (/sitemap.xml) stays in place for other
 * crawlers; this one is what gets submitted to GSC. Same data source
 * (buildSitemapEntries), so the two cannot drift.
 */
export async function GET(): Promise<Response> {
  const entries = await buildSitemapEntries();

  const urls = entries.map((entry) => {
    const lines = ['  <url>', `    <loc>${xmlEscape(entry.url)}</loc>`];
    const languages = entry.alternates?.languages ?? {};
    for (const [hreflang, href] of Object.entries(languages)) {
      lines.push(
        `    <xhtml:link rel="alternate" hreflang="${xmlEscape(hreflang)}" href="${xmlEscape(String(href))}" />`,
      );
    }
    if (entry.lastModified) {
      const iso =
        entry.lastModified instanceof Date
          ? entry.lastModified.toISOString()
          : String(entry.lastModified);
      lines.push(`    <lastmod>${xmlEscape(iso)}</lastmod>`);
    }
    if (entry.changeFrequency) {
      lines.push(`    <changefreq>${entry.changeFrequency}</changefreq>`);
    }
    if (entry.priority !== undefined) {
      lines.push(`    <priority>${entry.priority}</priority>`);
    }
    lines.push('  </url>');
    return lines.join('\n');
  });

  const body = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ...urls,
    '</urlset>',
    '',
  ].join('\n');

  return new Response(body, {
    headers: {
      'Content-Type': 'application/xml; charset=utf-8',
      'Cache-Control': 'public, max-age=86400, s-maxage=86400',
    },
  });
}
