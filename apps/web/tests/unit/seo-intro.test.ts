import { describe, expect, it } from 'vitest';
import { listJoin, stationNames, topByFrequency } from '@/lib/seo-intro';

describe('listJoin', () => {
  it('une con "y" en español y "and" en inglés', () => {
    expect(listJoin('es', ['A', 'B', 'C'])).toBe('A, B y C');
    expect(listJoin('en', ['A', 'B', 'C'])).toBe('A, B, and C');
    expect(listJoin('es', ['A'])).toBe('A');
    expect(listJoin('es', [])).toBe('');
  });
});

describe('topByFrequency', () => {
  it('ordena por frecuencia, ignora vacíos y respeta el límite', () => {
    expect(topByFrequency(['a', 'b', 'b', null, '', ' b ', 'c', 'c', 'a'], 2)).toEqual(['b', 'a']);
  });
});

describe('stationNames', () => {
  const s = (name: string) => ({ name });

  it('quita repetidos (sin distinguir mayúsculas) y respeta el límite', () => {
    expect(stationNames([s('Kiss FM'), s('kiss fm'), s('Radio X'), s('Radio Y'), s('Radio Z')], 3)).toEqual([
      'Kiss FM',
      'Radio X',
      'Radio Y',
    ]);
  });

  it('descarta nombres que empiezan por símbolo y conserva letras, dígitos y acentos', () => {
    expect(
      stationNames(
        [s('#join the party'), s('@dj'), s('* Radio *'), s('[HD] Mix'), s('106.5 Kiss'), s('Éter FM'), s('Радио Рекорд'), s('Chunt FM')],
        8,
      ),
    ).toEqual(['106.5 Kiss', 'Éter FM', 'Радио Рекорд', 'Chunt FM']);
  });

  it('descarta nombres larguísimos o con aspecto de URL (rótulos publicitarios)', () => {
    expect(
      stationNames(
        [
          s('Minimal Techno Radio & Track Discovery - ROminimal.club'),
          s('Visita www.ejemplo.net ya'),
          s('https://x.y/stream'),
          s('X'.repeat(41)),
          s('Radio Buena'),
        ],
        3,
      ),
    ).toEqual(['Radio Buena']);
  });

  it('devuelve [] si no queda ninguno aceptable', () => {
    expect(stationNames([s('')], 3)).toEqual([]);
    expect(stationNames([], 3)).toEqual([]);
  });
});
