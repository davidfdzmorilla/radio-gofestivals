import { describe, expect, it } from 'vitest';
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
        const title = (block as Record<string, unknown>)?.metaTitle;
        if (typeof title === 'string' && title.includes('radio.gofestivals')) {
          offenders.push(ns);
        }
      }
      // home.metaTitle es el título por defecto (sin template): sí lleva marca.
      expect(offenders.filter((ns) => ns !== 'home')).toEqual([]);
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

    it(`${locale}: el título de un género largo no pasa de 75 con el template`, () => {
      const raw = m.genres.metaTitle
        .replace('{name}', 'Progressive House')
        .replace(/\{count, plural,.*other \{# ([^}]*)\}\}/, '470 $1');
      expect(`${raw} · radio.gofestivals`.length).toBeLessThanOrEqual(75);
    });
  }
});
