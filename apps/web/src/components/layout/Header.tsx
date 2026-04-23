import { getTranslations } from 'next-intl/server';
import { Link } from '@/i18n/navigation';
import { LocaleSwitcher } from './LocaleSwitcher';

export async function Header() {
  const t = await getTranslations('nav');
  const tHome = await getTranslations('home');
  return (
    <header className="sticky top-0 z-40 border-b border-fg-3/40 bg-bg-1/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4">
        <Link
          href="/"
          className="group inline-flex items-center gap-2 -rotate-1 font-display text-lg font-semibold text-fg-0 transition-transform duration-200 hover:rotate-0"
        >
          <span
            aria-hidden
            className="inline-block h-2.5 w-2.5 rounded-full bg-magenta shadow-[0_0_0_3px_rgba(230,45,233,0.18)]"
          />
          {tHome('title')}
        </Link>
        <nav className="flex items-center gap-5 text-sm">
          <Link
            href="/"
            className="font-medium text-fg-1 underline decoration-transparent decoration-2 underline-offset-4 transition-colors hover:text-fg-0 hover:decoration-magenta"
          >
            {t('home')}
          </Link>
          <LocaleSwitcher />
        </nav>
      </div>
    </header>
  );
}
