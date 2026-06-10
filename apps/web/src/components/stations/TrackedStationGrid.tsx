'use client';

import { useEffect, useRef } from 'react';
import { useTranslations } from 'next-intl';
import type { Genre, StationSummary } from '@/lib/types';
import { readClientId } from '@/lib/plays';
import { sendRecEvents, type RecSurface } from '@/lib/recs';
import { StationCard } from './StationCard';

interface Props {
  stations: StationSummary[];
  genresBySlug: Record<string, Genre>;
  surface: RecSurface;
  maxCols?: 2 | 3;
}

/**
 * StationGrid con instrumentación de recomendaciones: una impresión por
 * tarjeta al montar y un click por interacción (rec_events, ver
 * docs/recommendations-plan.md §7). Sin client_id (no consent) no se
 * envía nada y el grid funciona igual.
 */
export function TrackedStationGrid({
  stations,
  genresBySlug,
  surface,
  maxCols = 3,
}: Props) {
  const tCommon = useTranslations('common');
  const tStation = useTranslations('station');
  const impressionsSent = useRef(false);

  useEffect(() => {
    if (impressionsSent.current || stations.length === 0) return;
    impressionsSent.current = true;
    sendRecEvents({
      surface,
      clientId: readClientId(),
      events: stations.map((s, i) => ({
        station_id: s.id,
        event_type: 'impression' as const,
        slot: i,
      })),
    });
  }, [stations, surface]);

  if (stations.length === 0) return null;

  const gridCols =
    maxCols === 2
      ? 'grid-cols-1 sm:grid-cols-2'
      : 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3';

  return (
    <div className={`grid gap-5 ${gridCols}`}>
      {stations.map((station, index) => (
        <div
          key={station.id}
          onClickCapture={() => {
            sendRecEvents({
              surface,
              clientId: readClientId(),
              events: [
                { station_id: station.id, event_type: 'click', slot: index },
              ],
            });
          }}
        >
          <StationCard
            station={station}
            genresBySlug={genresBySlug}
            index={index}
            labels={{
              curated: tCommon('curated'),
              location: ({ city, country }) =>
                tStation('location', { city, country }),
            }}
          />
        </div>
      ))}
    </div>
  );
}
