import type { Metadata } from 'next';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { LegalDocument, type LegalDocumentContent } from '@/components/legal/LegalDocument';
import { buildAlternates } from '@/lib/seo';
import { SITE_URL } from '@/lib/site';
import cookiesEs from '@/content/legal/cookies.es.json';
import cookiesEn from '@/content/legal/cookies.en.json';

export const revalidate = 86_400;

const CONTENT: Record<'es' | 'en', LegalDocumentContent> = {
  es: cookiesEs as LegalDocumentContent,
  en: cookiesEn as LegalDocumentContent,
};

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const tLegal = await getTranslations({ locale, namespace: 'legal' });
  const tHome = await getTranslations({ locale, namespace: 'home' });
  const title = tLegal('cookiesTitle');
  const url = `${SITE_URL}/${locale}/legal/cookies`;
  return {
    title,
    description: title,
    alternates: buildAlternates(locale, '/legal/cookies'),
    openGraph: {
      type: 'article',
      title,
      url,
      locale,
      siteName: tHome('title'),
    },
    robots: { index: true, follow: true },
  };
}

export default async function CookiesPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const tLegal = await getTranslations({ locale, namespace: 'legal' });
  const content = locale === 'en' ? CONTENT.en : CONTENT.es;
  return (
    <LegalDocument
      title={tLegal('cookiesTitle')}
      content={content}
      locale={locale as 'es' | 'en'}
    />
  );
}
