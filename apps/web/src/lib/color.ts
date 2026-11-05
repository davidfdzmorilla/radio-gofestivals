// Contraste WCAG para colores de género sobre el fondo oscuro de la app.
// Los colores de género (color_hex) vienen de la base de datos y varios no
// llegan a 4.5:1 (texto normal, AA) sobre bg-3: "Drum & Bass" daba 2.31.

/** Fondo más claro sobre el que se pinta texto de color (--bg-3). Es el caso más exigente. */
export const CHIP_BG = '#2b2924';
/** Tintas de texto sobre una superficie de color (--bg-0 / --fg-0). */
const INK_DARK = '#0c0b09';
const INK_LIGHT = '#fafaf9';

type RGB = [number, number, number];

function parseHex(hex: string): RGB | null {
  const m = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return null;
  let h = m[1]!;
  if (h.length === 3) h = [...h].map((c) => c + c).join('');
  const n = parseInt(h, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function toHex([r, g, b]: RGB): string {
  return '#' + [r, g, b].map((v) => Math.round(v).toString(16).padStart(2, '0')).join('');
}

function luminance([r, g, b]: RGB): number {
  const [R, G, B] = [r, g, b].map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  }) as RGB;
  return 0.2126 * R + 0.7152 * G + 0.0722 * B;
}

export function contrastRatio(a: string, b: string): number {
  const ca = parseHex(a);
  const cb = parseHex(b);
  if (!ca || !cb) return 1;
  const [hi, lo] = [luminance(ca), luminance(cb)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

/**
 * Devuelve `hex` o, si no llega a `min`, el mismo color aclarado hacia blanco
 * lo justo para alcanzarlo (conserva el tono). Hex inválido → tinta clara.
 */
export function readableOnDark(hex: string, bg: string = CHIP_BG, min = 4.5): string {
  const rgb = parseHex(hex);
  if (!rgb) return INK_LIGHT;
  if (contrastRatio(hex, bg) >= min) return toHex(rgb);
  for (let t = 0.05; t <= 1; t += 0.05) {
    const mixed = rgb.map((v) => v + (255 - v) * t) as RGB;
    if (contrastRatio(toHex(mixed), bg) >= min) return toHex(mixed);
  }
  return INK_LIGHT;
}

/** Tinta (oscura o clara) con mejor contraste sobre una superficie de color. */
export function readableTextOn(bg: string): string {
  return contrastRatio(INK_DARK, bg) >= contrastRatio(INK_LIGHT, bg) ? INK_DARK : INK_LIGHT;
}
