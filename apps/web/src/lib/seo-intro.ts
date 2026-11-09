/**
 * Piezas para las introducciones de género, país y país×género (T4, ADR 015). Todo sale de datos
 * reales de la página (números, subgéneros, ciudades, nombres de emisoras): así cada texto es
 * distinto y no hay párrafos genéricos repetidos entre páginas.
 */

/** "A, B y C" / "A, B and C" según el idioma. */
export function listJoin(locale: string, items: string[]): string {
  if (items.length === 0) return '';
  try {
    return new Intl.ListFormat(locale, { style: 'long', type: 'conjunction' }).format(items);
  } catch {
    return items.join(', ');
  }
}

/** Valores más frecuentes (sin vacíos), de mayor a menor; en empate, orden de primera aparición. */
export function topByFrequency(values: Array<string | null | undefined>, limit: number): string[] {
  const counts = new Map<string, number>();
  for (const v of values) {
    const key = v?.trim();
    if (key) counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([k]) => k);
}

const MAX_NAME_LENGTH = 40;

/**
 * Nombres para citar en un texto: sin repetidos (el catálogo tiene duplicados), sin nombres
 * larguísimos ni con aspecto de URL (rótulos publicitarios) y sin ciudad: el campo `city` de
 * Radio-Browser trae regiones ("NRW", "Sachsen") y no es fiable para una frase.
 */
export function stationNames(stations: Array<{ name: string }>, limit: number): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const { name } of stations) {
    const clean = name.trim();
    const key = clean.toLowerCase();
    if (!clean || clean.length > MAX_NAME_LENGTH || /https?:|www\.|\.(com|net|org|club|fm|es|de)\b/i.test(clean)) continue;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(clean);
    if (out.length >= limit) break;
  }
  return out;
}
