import { NextRequest } from 'next/server';
import { describe, expect, it } from 'vitest';
import { proxy } from '@/proxy';

const call = (path: string, headers: Record<string, string> = {}) =>
  proxy(new NextRequest(`https://radio.gofestivals.eu${path}`, { headers }));

describe('proxy: rutas sin prefijo de idioma', () => {
  it.each(['/countries/ro/deep-house', '/countries/ro', '/genres/techno', '/stations/radio-x'])(
    '%s -> 308 de un solo salto a la versión con idioma, sin cachear',
    (path) => {
      const res = call(path);
      expect(res.status).toBe(308);
      const target = new URL(res.headers.get('location')!, 'https://radio.gofestivals.eu');
      expect(target.pathname).toBe(`/es${path}`);
      expect(res.headers.get('cache-control')).toBe('private, no-store');
    },
  );

  it('respeta Accept-Language al elegir el idioma de destino', () => {
    const res = call('/genres/techno', { 'accept-language': 'en-GB,en;q=0.9' });
    expect(res.status).toBe(308);
    expect(new URL(res.headers.get('location')!, 'https://x').pathname).toBe('/en/genres/techno');
  });

  it('las rutas ya con idioma no se redirigen', () => {
    const res = call('/es/countries/ro');
    expect(res.status).not.toBe(308);
    expect(res.headers.get('location')).toBeNull();
  });

  it('la portada / sigue negociando el idioma: 307 sin caché, nunca un 308 fijo', () => {
    const es = call('/');
    expect(es.status).toBe(307);
    expect(es.headers.get('cache-control')).toBe('private, no-store');
    expect(new URL(es.headers.get('location')!, 'https://x').pathname).toBe('/es');
    const en = call('/', { 'accept-language': 'en-GB,en;q=0.9' });
    expect(en.status).toBe(307);
    expect(new URL(en.headers.get('location')!, 'https://x').pathname).toBe('/en');
  });
});
