import type { Metadata } from 'next';
import { getTranslations } from 'next-intl/server';
import { buildAlternates } from '@/lib/seo';

// Página de utilidad sin contenido propio que posicionar: fuera del sitemap y
// con noindex. Sin metadata propia heredaba título y canonical de la home, y
// Google la veía como duplicado.
export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: 'auth' });
  return {
    title: t('support'),
    alternates: buildAlternates(locale, '/support'),
    robots: { index: false },
  };
}

export default function SupportLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
