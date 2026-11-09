import type { MetadataRoute } from 'next';

const SITE = 'https://radio.gofestivals.eu';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: '*',
        // Googlebot aplica la regla más específica: el logo (que va en el JSON-LD de
        // la emisora) tiene que poder rastrearse aunque /api/ esté vetado.
        allow: ['/', '/api/v1/stations/*/logo'],
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
    sitemap: `${SITE}/sitemap.xml`,
  };
}
