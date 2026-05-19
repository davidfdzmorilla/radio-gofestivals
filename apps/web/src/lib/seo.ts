import type { Metadata } from 'next';
import { SITE_URL } from './site';

const LOCALES = ['en', 'es'] as const;
const X_DEFAULT_LOCALE: (typeof LOCALES)[number] = 'en';

/**
 * Builds absolute canonical + hreflang alternates for a locale-prefixed page.
 * `pathWithoutLocale` is the path after the locale: `''` for the home,
 * `/genres/techno` for a genre, etc. Without per-page overrides, Next.js'
 * shallow-merge leaks the layout's home alternates onto every child route —
 * which silently dedupes them all to the home in Google's index.
 */
export function buildAlternates(
  locale: string,
  pathWithoutLocale: string,
): NonNullable<Metadata['alternates']> {
  const languages: Record<string, string> = {};
  for (const l of LOCALES) {
    languages[l] = `${SITE_URL}/${l}${pathWithoutLocale}`;
  }
  languages['x-default'] = `${SITE_URL}/${X_DEFAULT_LOCALE}${pathWithoutLocale}`;
  return {
    canonical: `${SITE_URL}/${locale}${pathWithoutLocale}`,
    languages,
  };
}
