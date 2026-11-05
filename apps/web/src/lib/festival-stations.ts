import { listStations } from '@/lib/api';
import { allocateSlots, type GenreWeight } from '@/lib/festival-genres';
import type { StationSummary } from '@/lib/types';

const SPARE = 4;

/**
 * Emisoras "para calentar" un festival: se reparten los huecos entre sus géneros
 * principales (más peso, más emisoras) y se pide a la radio las de cada género.
 * Fail-soft: un género que falla se omite; si todos fallan, lista vacía.
 */
export async function stationsForFestival(
  weights: readonly GenreWeight[],
  total = 6,
): Promise<StationSummary[]> {
  const plan = allocateSlots(weights, total);
  const pages = await Promise.all(
    plan.map((p) =>
      // Margen para poder saltar las que ya salieron por otro género.
      listStations({ genre: p.slug, size: p.count + SPARE, revalidate: 300 }).then(
        (page) => page.items,
        () => [] as StationSummary[],
      ),
    ),
  );

  const picked: StationSummary[] = [];
  const seen = new Set<string>();
  const take = (items: StationSummary[], n: number) => {
    for (const s of items) {
      if (n <= 0) break;
      if (seen.has(s.id)) continue;
      seen.add(s.id);
      picked.push(s);
      n -= 1;
    }
  };
  pages.forEach((items, i) => take(items, plan[i]!.count));
  // Si los duplicados dejaron huecos, se rellenan con lo que sobró, en orden de peso.
  if (picked.length < total) pages.forEach((items) => take(items, total - picked.length));
  return picked;
}
