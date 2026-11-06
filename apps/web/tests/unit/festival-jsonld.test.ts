import { describe, expect, it } from 'vitest';
import { festivalEventLd } from '@/lib/festival-jsonld';
import type { Festival } from '@/lib/festivals';

function fest(over: Partial<Festival> = {}): Festival {
  return {
    id: '29',
    name: 'Airbeat One',
    startDate: '2027-07-07T00:00:00.000Z',
    endDate: '2027-07-11T00:00:00.000Z',
    location: 'Neustadt-Glewe, Alemania',
    locationEn: 'Neustadt-Glewe, Germany',
    countryCode: 'DE',
    website: 'https://airbeat-one.de',
    imageUrl: 'https://proyecto-images-gofestivals.s3.eu-west-3.amazonaws.com/festivals/x.jpg',
    description: 'Gran festival.',
    descriptionEn: 'Big festival.',
    genres: ['House'],
    ...over,
  };
}

describe('festivalEventLd', () => {
  it('emite un Event con fechas sin hora, lugar localizado y URL canónica', () => {
    const ld = festivalEventLd(fest(), 'en')!;
    expect(ld['@type']).toBe('Event');
    expect(ld.startDate).toBe('2027-07-07');
    expect(ld.endDate).toBe('2027-07-11');
    expect(ld.location).toEqual({
      '@type': 'Place',
      name: 'Neustadt-Glewe, Germany',
      address: { '@type': 'PostalAddress', addressCountry: 'DE' },
    });
    expect(ld.url).toBe('https://radio.gofestivals.eu/en/festivals/29/airbeat-one');
    expect(ld.description).toBe('Big festival.');
    expect(ld.sameAs).toBe('https://airbeat-one.de/');
  });

  it('usa el texto en español en es', () => {
    const ld = festivalEventLd(fest(), 'es')!;
    expect((ld.location as { name: string }).name).toBe('Neustadt-Glewe, Alemania');
    expect(ld.description).toBe('Gran festival.');
  });

  it('emite image con la URL de la ficha si es de un host de gofestivals', () => {
    expect(festivalEventLd(fest(), 'es')!.image).toEqual([
      'https://proyecto-images-gofestivals.s3.eu-west-3.amazonaws.com/festivals/x.jpg',
    ]);
    const api = 'https://api.gofestivals.es/uploads/festivals/23-5046bc67ea.jpg';
    expect(festivalEventLd(fest({ imageUrl: api }), 'es')!.image).toEqual([api]);
  });

  it('no emite image si falta o el host no está permitido', () => {
    expect(festivalEventLd(fest({ imageUrl: null }), 'es')).not.toHaveProperty('image');
    expect(festivalEventLd(fest({ imageUrl: 'https://evil.example/festivals/x.jpg' }), 'es')).not.toHaveProperty('image');
  });

  it('sin lugar o sin fecha válida no emite nada', () => {
    expect(festivalEventLd(fest({ location: null, locationEn: null }), 'es')).toBeNull();
    expect(festivalEventLd(fest({ location: '  ', locationEn: null }), 'es')).toBeNull();
    expect(festivalEventLd(fest({ startDate: 'basura' }), 'es')).toBeNull();
  });

  it('sin país usa el texto como dirección', () => {
    const ld = festivalEventLd(fest({ countryCode: null }), 'es')!;
    expect((ld.location as { address: unknown }).address).toBe('Neustadt-Glewe, Alemania');
  });

  it('omite endDate si falta, es inválida o anterior al inicio', () => {
    for (const endDate of [null, 'basura', '2027-07-01T00:00:00.000Z']) {
      expect(festivalEventLd(fest({ endDate }), 'es')).not.toHaveProperty('endDate');
    }
  });

  it('descarta webs que no son http(s) y recorta descripciones largas', () => {
    expect(festivalEventLd(fest({ website: 'javascript:alert(1)' }), 'es')).not.toHaveProperty('sameAs');
    const ld = festivalEventLd(fest({ description: 'x'.repeat(900) }), 'es')!;
    expect((ld.description as string).length).toBe(500);
  });
});
