'use client';

import { useLocale, useTranslations } from 'next-intl';
import { Globe } from 'lucide-react';
import { useRouter, usePathname } from '@/i18n/navigation';
import { routing } from '@/i18n/routing';

export function LocaleSwitcher() {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const t = useTranslations('nav');

  return (
    <label className="flex items-center gap-1.5 text-sm text-white/70">
      <Globe className="h-4 w-4" aria-hidden />
      <span className="sr-only">{t('language')}</span>
      <select
        aria-label={t('language')}
        value={locale}
        className="bg-transparent text-white outline-none focus:ring-2 focus:ring-wave"
        onChange={(e) => {
          const next = e.target.value as (typeof routing.locales)[number];
          router.replace(pathname, { locale: next });
        }}
      >
        {routing.locales.map((loc) => (
          <option key={loc} value={loc} className="bg-ink">
            {loc.toUpperCase()}
          </option>
        ))}
      </select>
    </label>
  );
}
