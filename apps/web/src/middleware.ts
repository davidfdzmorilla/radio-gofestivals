import createMiddleware from 'next-intl/middleware';
import { routing } from './i18n/routing';

export default createMiddleware(routing);

export const config = {
  // Skip /admin so it stays out of next-intl's locale routing — the admin
  // shell renders without the /es,/en prefix and manages its own auth.
  matcher: [
    '/',
    '/(en|es)/:path*',
    '/((?!_next|_vercel|api|admin|.*\\..*).*)',
  ],
};
