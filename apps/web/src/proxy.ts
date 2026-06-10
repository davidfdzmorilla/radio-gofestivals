import createMiddleware from 'next-intl/middleware';
import { routing } from './i18n/routing';

// Next 16: middleware.ts queda deprecado; proxy.ts corre en runtime
// nodejs y exporta la función con nombre `proxy`.
export const proxy = createMiddleware(routing);

export const config = {
  // Skip /admin so it stays out of next-intl's locale routing — the admin
  // shell renders without the /es,/en prefix and manages its own auth.
  matcher: [
    '/',
    '/(en|es)/:path*',
    '/((?!_next|_vercel|api|admin|.*\\..*).*)',
  ],
};
