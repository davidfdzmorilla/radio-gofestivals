import { describe, expect, it } from 'vitest';
import {
  CHIP_BG,
  contrastRatio,
  readableOnDark,
  readableTextOn,
} from '@/lib/color';

// Colores de género reales de producción (los que fallaban) y extremos.
const GENRE_COLORS = [
  '#8B4EE8', '#E62DE9', '#1CC1F9', '#A01AA8', '#2A1A5E', '#5B21B6', '#16A34A',
  '#F59E0B', '#EF4444', '#FDE047', '#000000', '#0c0b09', '#2b2924', '#ffffff',
];

describe('contrastRatio', () => {
  it('matches the WCAG reference values', () => {
    expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21, 1);
    expect(contrastRatio('#777777', '#777777')).toBeCloseTo(1, 5);
  });
  it('returns 1 for invalid input instead of throwing', () => {
    expect(contrastRatio('nope', '#fff')).toBe(1);
  });
});

describe('readableOnDark', () => {
  it.each(GENRE_COLORS)('%s reaches 4.5:1 on the chip background', (hex) => {
    expect(contrastRatio(readableOnDark(hex), CHIP_BG)).toBeGreaterThanOrEqual(4.5);
  });

  it('leaves already-readable colors untouched', () => {
    expect(readableOnDark('#FDE047').toLowerCase()).toBe('#fde047');
  });

  it('lightens a low-contrast color but keeps its hue family', () => {
    const out = readableOnDark('#A01AA8'); // magenta oscuro, ~2.3:1
    expect(out.toLowerCase()).not.toBe('#a01aa8');
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(out.slice(i, i + 2), 16)) as [number, number, number];
    expect(r).toBeGreaterThan(g); // sigue siendo magenta/rosa, no gris
    expect(b).toBeGreaterThan(g);
  });

  it('falls back to a light ink for invalid hex', () => {
    expect(readableOnDark('not-a-color').toLowerCase()).toBe('#fafaf9');
  });

  it('accepts 3-digit hex', () => {
    expect(contrastRatio(readableOnDark('#a0a'), CHIP_BG)).toBeGreaterThanOrEqual(4.5);
  });
});

describe('readableTextOn', () => {
  it('picks dark ink on light surfaces and light ink on dark ones', () => {
    expect(readableTextOn('#FDE047')).toBe('#0c0b09');
    expect(readableTextOn('#2A1A5E')).toBe('#fafaf9');
  });
  it.each(GENRE_COLORS)('always beats 4.5:1 or the best available on %s', (hex) => {
    const ink = readableTextOn(hex);
    expect(contrastRatio(ink, hex)).toBeGreaterThanOrEqual(4.5);
  });
});
