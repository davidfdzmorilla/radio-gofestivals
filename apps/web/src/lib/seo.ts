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
/**
 * Publication gate for programmatic country pages: below this station count
 * the page is neither generated nor listed in the sitemap (thin content).
 * Both consumers MUST read the same constant so they never diverge.
 */
export const COUNTRY_GATE_MIN_STATIONS = 3;

/**
 * Same idea for per-genre trending pages: /trending/{genre} only exists
 * (page + sitemap) for root genres with at least this many stations.
 */
export const TRENDING_GENRE_GATE_MIN = 10;

/**
 * Country×genre combo pages (/countries/{iso2}/{genre}): the longtail core
 * of the programmatic layer, and also its biggest thin-content risk — a
 * combo with 2 stations is exactly the page Helpful Content demotes.
 */
export const COMBO_GATE_MIN_STATIONS = 5;

/** Localized country name from its ISO code, falling back to the code. */
export function regionName(locale: string, code: string): string {
  try {
    return (
      new Intl.DisplayNames([locale], { type: 'region' }).of(
        code.toUpperCase(),
      ) ?? code.toUpperCase()
    );
  } catch {
    return code.toUpperCase();
  }
}

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
