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
    <label className="inline-flex items-center gap-2 rounded-full border border-fg-3 bg-bg-2 px-3 py-1.5 text-sm text-fg-1 transition-colors hover:border-magenta/70 hover:text-fg-0">
      <Globe className="h-3.5 w-3.5 text-fg-2" aria-hidden />
      <span className="sr-only">{t('language')}</span>
      <select
        aria-label={t('language')}
        value={locale}
        className="bg-transparent text-fg-0 outline-none"
        onChange={(e) => {
          const next = e.target.value as (typeof routing.locales)[number];
          router.replace(pathname, { locale: next });
        }}
      >
        {routing.locales.map((loc) => (
          <option key={loc} value={loc} className="bg-bg-1 text-fg-0">
            {loc.toUpperCase()}
          </option>
        ))}
      </select>
    </label>
  );
}
