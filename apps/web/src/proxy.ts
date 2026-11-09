import createMiddleware from 'next-intl/middleware';
import { NextResponse, type NextRequest } from 'next/server';
import { routing } from './i18n/routing';

const intl = createMiddleware(routing);

// Next 16: middleware.ts queda deprecado; proxy.ts corre en runtime
// nodejs y exporta la función con nombre `proxy`.
//
// next-intl redirige las rutas sin prefijo de idioma (`/countries/ro` → `/es/countries/ro`) con
// 307. Para Google un 307 es temporal y mantiene la URL sin prefijo como candidata; el destino
// es siempre la versión con idioma, así que se emite 308 (permanente, un solo salto). Como el
// idioma elegido depende de la cookie y de Accept-Language, se prohíbe cachear el redirect:
// un navegador no debe fijar un idioma para siempre.
export function proxy(request: NextRequest) {
  const response = intl(request);
  if (response.status !== 307) return response;
  const headers = new Headers(response.headers);
  headers.set('cache-control', 'private, no-store');
  return new NextResponse(null, { status: 308, headers });
}

export const config = {
  // Skip /admin so it stays out of next-intl's locale routing — the admin
  // shell renders without the /es,/en prefix and manages its own auth.
  matcher: [
    '/',
    '/(en|es)/:path*',
    '/((?!_next|_vercel|api|admin|.*\\..*).*)',
  ],
};
