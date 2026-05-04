import type { Metadata } from 'next';
import { NextIntlClientProvider } from 'next-intl';
import { getMessages, getTranslations, setRequestLocale } from 'next-intl/server';
import { JetBrains_Mono } from 'next/font/google';
import { notFound } from 'next/navigation';
import { routing } from '@/i18n/routing';
import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import { GlobalPlayer } from '@/components/player/GlobalPlayer';
import { ToastProvider } from '@/components/auth/ToastContext';
import { AuthProvider } from '@/lib/users/AuthContext';
import '../globals.css';

const mono = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-mono',
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
    alternates: {
      canonical: `/${locale}`,
      languages: {
        en: '/en',
        es: '/es',
      },
    },
    openGraph: {
      type: 'website',
      title: t('title'),
      description: t('seoDescription'),
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

  const messages = await getMessages();

  return (
    <html lang={locale} className={mono.variable}>
      <head>
        <link rel="preconnect" href="https://api.fontshare.com" />
        <link rel="preconnect" href="https://cdn.fontshare.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://api.fontshare.com/v2/css?f[]=chillax@500,600,700&f[]=satoshi@400,500&display=swap"
        />
      </head>
      <body className="min-h-screen bg-bg-1 text-fg-1 font-body antialiased">
        <NextIntlClientProvider messages={messages}>
          <AuthProvider>
            <ToastProvider>
              <Header />
              <main className="mx-auto max-w-6xl px-4 py-10 pb-32">
                {children}
              </main>
              <Footer />
              <GlobalPlayer />
            </ToastProvider>
          </AuthProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
