import { getTranslations } from 'next-intl/server';

export async function Footer({ locale }: { locale: 'es' | 'en' }) {
  const tHome = await getTranslations({ locale, namespace: 'home' });
  const tLegal = await getTranslations({ locale, namespace: 'legal' });
  const tNav = await getTranslations({ locale, namespace: 'nav' });
  return (
    <footer className="mt-20 border-t border-fg-3/30 px-4 py-8">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-3 text-center sm:flex-row sm:justify-between">
        <p className="font-display text-sm font-medium text-fg-1">
          <span className="mr-2 inline-block h-2 w-2 -translate-y-0.5 rounded-full bg-magenta align-middle" />
          {tHome('title')}
        </p>
        <nav className="flex flex-wrap items-center justify-center gap-x-4 font-mono text-[12px] uppercase tracking-widest text-fg-2">
          <a
            href={`/${locale}/countries`}
            className="py-2 transition-colors hover:text-fg-0"
          >
            {tNav('countries')}
          </a>
          <span aria-hidden className="hidden sm:inline">
            ·
          </span>
          <a
            href={`/${locale}/trending`}
            className="py-2 transition-colors hover:text-fg-0"
          >
            {tNav('trending')}
          </a>
          <span aria-hidden className="hidden sm:inline">
            ·
          </span>
          <a
            href={`/${locale}/new`}
            className="py-2 transition-colors hover:text-fg-0"
          >
            {tNav('new')}
          </a>
          <span aria-hidden className="hidden sm:inline">
            ·
          </span>
          <a
            href={`/${locale}/for-stations`}
            className="py-2 transition-colors hover:text-fg-0"
          >
            {tNav('forStations')}
          </a>
          <span aria-hidden className="hidden sm:inline">
            ·
          </span>
          <a
            href={`/${locale}/legal/privacy`}
            className="py-2 transition-colors hover:text-fg-0"
          >
            {tLegal('privacyLink')}
          </a>
          <span aria-hidden className="hidden sm:inline">
            ·
          </span>
          <a
            href={`/${locale}/legal/cookies`}
            className="py-2 transition-colors hover:text-fg-0"
          >
            {tLegal('cookiesLink')}
          </a>
        </nav>
        <p className="font-mono text-[12px] uppercase tracking-widest text-fg-2">
          © {new Date().getFullYear()} · gofestivals
        </p>
      </div>
    </footer>
  );
}
