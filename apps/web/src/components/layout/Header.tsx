import Image from 'next/image';
import { Search } from 'lucide-react';
import { getTranslations } from 'next-intl/server';
import { Link } from '@/i18n/navigation';
import { HeaderAuth } from '@/components/auth/HeaderAuth';
import { MobileMenu } from '@/components/auth/MobileMenu';
import { SearchBox } from '@/components/search/SearchBox';
import { LocaleSwitcher } from './LocaleSwitcher';

export async function Header() {
  const t = await getTranslations('nav');
  const tHome = await getTranslations('home');
  const tSearch = await getTranslations('search');
  return (
    <header className="sticky top-0 z-40 border-b border-fg-3/40 bg-bg-1/90 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4">
        <Link
          href="/"
          className="group inline-flex items-center gap-2 -rotate-1 font-display text-lg font-semibold text-fg-0 transition-transform duration-200 hover:rotate-0"
        >
          <Image
            src="/gofestivals-logo.png"
            alt=""
            aria-hidden
            width={954}
            height={748}
            sizes="46px"
            priority
            className="h-9 w-auto"
          />
          {/* En md el header va justo con los 5 links + buscador: el texto
              del brand solo cabe en lg+ (y en móvil, donde no hay nav). */}
          <span className="md:hidden lg:inline">{tHome('title')}</span>
        </Link>
        <nav className="hidden items-center gap-5 text-sm md:flex">
          <Link
            href="/"
            className="font-medium text-fg-1 underline decoration-transparent decoration-2 underline-offset-4 transition-colors hover:text-fg-0 hover:decoration-magenta"
          >
            {t('home')}
          </Link>
          <Link
            href="/genres"
            className="font-medium text-fg-1 underline decoration-transparent decoration-2 underline-offset-4 transition-colors hover:text-fg-0 hover:decoration-magenta"
          >
            {t('genres')}
          </Link>
          <Link
            href="/countries"
            className="font-medium text-fg-1 underline decoration-transparent decoration-2 underline-offset-4 transition-colors hover:text-fg-0 hover:decoration-magenta"
          >
            {t('countries')}
          </Link>
          <Link
            href="/trending"
            className="font-medium text-fg-1 underline decoration-transparent decoration-2 underline-offset-4 transition-colors hover:text-fg-0 hover:decoration-magenta"
          >
            {t('trending')}
          </Link>
          <Link
            href="/favorites"
            className="font-medium text-fg-1 underline decoration-transparent decoration-2 underline-offset-4 transition-colors hover:text-fg-0 hover:decoration-magenta"
          >
            {t('favorites')}
          </Link>
          {/* Typeahead solo en lg+: en md el header no tiene hueco para el
              input, así que se ofrece un icono-link a /search. */}
          <div className="hidden lg:block">
            <SearchBox variant="header" />
          </div>
          <Link
            href="/search"
            aria-label={tSearch('ariaLabel')}
            className="text-fg-1 transition-colors hover:text-fg-0 lg:hidden"
          >
            <Search size={18} />
          </Link>
          <LocaleSwitcher />
          <HeaderAuth />
        </nav>
        <MobileMenu />
      </div>
    </header>
  );
}
