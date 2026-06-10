import type { MetadataRoute } from 'next';

const SITE = 'https://radio.gofestivals.eu';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: [
          '/admin',
          '/api/',
          '/*/login',
          '/*/signup',
          '/*/forgot-password',
          '/*/reset-password',
          '/*/profile',
          '/*/favorites',
          '/*/verify-email',
        ],
      },
    ],
    sitemap: [`${SITE}/sitemap.xml`, `${SITE}/sitemap-v2.xml`],
    host: SITE,
  };
}
