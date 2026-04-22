import { defineRouting } from 'next-intl/routing';

const envDefault = process.env.NEXT_PUBLIC_DEFAULT_LOCALE;
const defaultLocale: 'en' | 'es' =
  envDefault === 'en' || envDefault === 'es' ? envDefault : 'es';

export const routing = defineRouting({
  locales: ['en', 'es'],
  defaultLocale,
  localePrefix: 'always',
});
