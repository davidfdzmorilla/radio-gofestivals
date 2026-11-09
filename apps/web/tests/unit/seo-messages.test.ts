import { describe, expect, it } from 'vitest';
import { pageTitle } from '@/lib/seo';
import en from '../../messages/en.json';
import es from '../../messages/es.json';

const LOCALES = { es, en } as const;

// El layout raíz añade ` · radio.gofestivals` a todo título (title.template).
// Si el mensaje ya la lleva, Google ve la marca dos veces y recorta el título.
describe('metadatos SEO en los mensajes', () => {
  for (const [locale, m] of Object.entries(LOCALES)) {
    it(`${locale}: los metaTitle no repiten la marca del template`, () => {
      const offenders: string[] = [];
      for (const [ns, block] of Object.entries(m)) {
        for (const key of ['metaTitle', 'indexTitle', 'indexMetaTitle']) {
          const title = (block as Record<string, unknown>)?.[key];
          if (typeof title === 'string' && title.includes('radio.gofestivals')) {
            offenders.push(`${ns}.${key}`);
          }
        }
      }
      // home.metaTitle es el título por defecto (sin template): sí lleva marca.
      expect(offenders.filter((k) => !k.startsWith('home.'))).toEqual([]);
    });

    it(`${locale}: las descripciones caben en un snippet (70-165)`, () => {
      const bad: string[] = [];
      const check = (key: string, v: unknown) => {
        if (typeof v === 'string' && !v.includes('{')) {
          if (v.length < 70 || v.length > 165) bad.push(`${key}=${v.length}`);
        }
      };
      check('home.seoDescription', m.home.seoDescription);
      for (const [ns, block] of Object.entries(m)) {
        check(`${ns}.metaDescription`, (block as Record<string, unknown>)?.metaDescription);
      }
      expect(bad).toEqual([]);
    });
  }
});

describe('pageTitle (regla de gofestivals.eu: con marca > 60 caracteres, sin marca)', () => {
  const BRAND_SUFFIX = ' · radio.gofestivals'.length; // 20

  it('deja el título como está si con la marca cabe en 60', () => {
    const title = 'x'.repeat(60 - BRAND_SUFFIX);
    expect(pageTitle(title)).toBe(title);
  });

  it('quita la marca (title.absolute) si con ella pasa de 60, sin recortar el contenido', () => {
    const title = 'x'.repeat(60 - BRAND_SUFFIX + 1);
    expect(pageTitle(title)).toEqual({ absolute: title });
    const long = 'Radio Progressive House: 470 emisoras online en directo';
    expect(pageTitle(long)).toEqual({ absolute: long });
  });
});
