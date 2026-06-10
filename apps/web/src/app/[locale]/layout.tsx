import type { Metadata } from 'next';
import { NextIntlClientProvider } from 'next-intl';
import { getMessages, getTranslations, setRequestLocale } from 'next-intl/server';
import { JetBrains_Mono } from 'next/font/google';
import localFont from 'next/font/local';
import { notFound } from 'next/navigation';
import { routing } from '@/i18n/routing';
import { JsonLd } from '@/components/seo/JsonLd';
import { SITE_URL } from '@/lib/site';
import { buildAlternates } from '@/lib/seo';
import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import { GlobalPlayer } from '@/components/player/GlobalPlayer';
import { ConsentBanner } from '@/components/consent/ConsentBanner';
import { ToastProvider } from '@/components/auth/ToastContext';
import { AuthProvider } from '@/lib/users/AuthContext';
import '../globals.css';

const mono = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-mono',
  display: 'swap',
});

// Chillax y Satoshi self-hosted (descargadas de Fontshare): sin conexión a
// CDN de terceros y con preload automático — la fuente es el LCP del sitio.
const chillax = localFont({
  src: [
    { path: '../../fonts/chillax-500.woff2', weight: '500' },
    { path: '../../fonts/chillax-600.woff2', weight: '600' },
    { path: '../../fonts/chillax-700.woff2', weight: '700' },
  ],
  variable: '--font-chillax',
  display: 'swap',
});

const satoshi = localFont({
  src: [
    { path: '../../fonts/satoshi-400.woff2', weight: '400' },
    { path: '../../fonts/satoshi-500.woff2', weight: '500' },
  ],
  variable: '--font-satoshi',
  display: 'swap',
});

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: 'home' });
  return {
    title: {
      default: t('title'),
      template: `%s · ${t('title')}`,
    },
    description: t('seoDescription'),
    alternates: buildAlternates(locale, ''),
    openGraph: {
      type: 'website',
      title: t('title'),
      description: t('seoDescription'),
      url: `${SITE_URL}/${locale}`,
      locale,
      siteName: t('title'),
    },
    twitter: {
      card: 'summary_large_image',
      title: t('title'),
      description: t('seoDescription'),
    },
    robots: { index: true, follow: true },
  };
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!(routing.locales as readonly string[]).includes(locale)) notFound();
  setRequestLocale(locale);

  const t = await getTranslations({ locale, namespace: 'home' });
  const messages = await getMessages();

  const websiteLd = {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: t('title'),
    url: `${SITE_URL}/${locale}`,
    description: t('seoDescription'),
    inLanguage: locale,
  };
  const organizationLd = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: t('title'),
    url: SITE_URL,
  };

  return (
    <html
      lang={locale}
      className={`${mono.variable} ${chillax.variable} ${satoshi.variable}`}
    >
      <body className="min-h-screen bg-bg-1 text-fg-1 font-body antialiased">
        <JsonLd data={websiteLd} />
        <JsonLd data={organizationLd} />
        <NextIntlClientProvider messages={messages}>
          <AuthProvider>
            <ToastProvider>
              <Header />
              <main className="mx-auto max-w-6xl px-4 py-10 pb-32">
                {children}
              </main>
              <Footer locale={locale as 'es' | 'en'} />
              <GlobalPlayer />
              <ConsentBanner locale={locale as 'es' | 'en'} />
            </ToastProvider>
          </AuthProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
