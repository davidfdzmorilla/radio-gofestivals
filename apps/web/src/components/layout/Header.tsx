import { getTranslations } from 'next-intl/server';
import { Link } from '@/i18n/navigation';
import { LocaleSwitcher } from './LocaleSwitcher';

export async function Header() {
  const t = await getTranslations('nav');
  const tHome = await getTranslations('home');
  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-ink/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <Link
          href="/"
          className="font-display text-lg font-bold text-white hover:text-magenta"
        >
          {tHome('title')}
        </Link>
        <nav className="flex items-center gap-4 text-sm text-white/70">
          <Link href="/" className="hover:text-white">
            {t('home')}
          </Link>
          <LocaleSwitcher />
        </nav>
      </div>
    </header>
  );
}
