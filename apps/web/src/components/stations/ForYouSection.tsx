'use client';

import { useEffect, useState } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import type { Genre, StationSummary } from '@/lib/types';
import { readClientId } from '@/lib/plays';
import { getRecommendedStations } from '@/lib/recs';
import { TrackedStationGrid } from './TrackedStationGrid';

interface Props {
  genresBySlug: Record<string, Genre>;
}

/**
 * Módulo "Para ti" de la home. Client-side a propósito: la respuesta es
 * personalizada por client_id (localStorage) y no puede ir en el ISR de
 * la página. Sin historial el backend devuelve el cold start del locale,
 * así que el módulo nunca queda vacío salvo error de red — en ese caso
 * se oculta entero en silencio.
 */
export function ForYouSection({ genresBySlug }: Props) {
  const locale = useLocale();
  const tHome = useTranslations('home');
  const [stations, setStations] = useState<StationSummary[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    getRecommendedStations({
      clientId: readClientId(),
      locale: typeof navigator !== 'undefined' ? navigator.language : locale,
      size: 12,
    })
      .then((page) => {
        if (!cancelled) setStations(page.items);
      })
      .catch(() => {
        if (!cancelled) setStations([]);
      });
    return () => {
      cancelled = true;
    };
  }, [locale]);

  if (stations === null || stations.length === 0) return null;

  return (
    <section className="space-y-5">
      <div className="flex items-baseline justify-between">
        <h2 className="font-display text-3xl font-semibold text-fg-0">
          <span className="mr-2 inline-block -rotate-1 rounded-lg bg-magenta px-2 py-0.5 text-fg-0 shadow-sticker-magenta">
            {tHome('forYou')}
          </span>
        </h2>
      </div>
      <TrackedStationGrid
        stations={stations}
        genresBySlug={genresBySlug}
        surface="home_for_you"
      />
    </section>
  );
}
