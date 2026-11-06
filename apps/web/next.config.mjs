import createNextIntlPlugin from 'next-intl/plugin';

const withNextIntl = createNextIntlPlugin('./src/i18n/request.ts');

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  images: {
    // Imágenes de festivales de gofestivals (ADR 009). Se sirven desde /_next/image,
    // así que la CSP (img-src 'self') no cambia. Mantener en sintonía con IMAGE_HOST
    // de src/lib/festivals.ts.
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'proyecto-images-gofestivals.s3.eu-west-3.amazonaws.com',
        pathname: '/festivals/**',
      },
      {
        protocol: 'https',
        hostname: 'api.gofestivals.es',
        pathname: '/uploads/festivals/**',
      },
    ],
  },
  experimental: {
    optimizePackageImports: ['lucide-react'],
  },
};

export default withNextIntl(nextConfig);
