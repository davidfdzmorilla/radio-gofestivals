'use client';

import { useEffect, useMemo, useState } from 'react';
import { PlayButton } from './PlayButton';
import { QualitySelector } from '@/components/player/QualitySelector';
import { usePlayerStore } from '@/lib/player-store';
import {
  findPreferredStream,
  persistQualityPreference,
} from '@/lib/quality';
import type { StationStreamRef, StationSummary } from '@/lib/types';

interface Props {
  baseSummary: Omit<StationSummary, 'primary_stream'>;
  streams: StationStreamRef[];
  color: string;
}

export function StationPlayerControls({ baseSummary, streams, color }: Props) {
  const initialStream = useMemo(() => {
    if (streams.length === 0) return null;
    return findPreferredStream(streams);
  }, [streams]);

  const [activeStreamId, setActiveStreamId] = useState<string | null>(
    initialStream?.id ?? null,
  );

  const currentStation = usePlayerStore((s) => s.currentStation);
  const setStream = usePlayerStore((s) => s.setStream);

  // If this very station is the one currently playing in the global player
  // and the user opens the detail page, mirror the live primary_stream so
  // the active pill matches what's actually being heard.
  useEffect(() => {
    if (
      currentStation &&
      currentStation.id === baseSummary.id &&
      currentStation.primary_stream
    ) {
      setActiveStreamId(currentStation.primary_stream.id);
    }
  }, [currentStation, baseSummary.id]);

  const summary: StationSummary = useMemo(() => {
    const stream =
      streams.find((s) => s.id === activeStreamId) ?? initialStream ?? null;
    return { ...baseSummary, primary_stream: stream };
  }, [baseSummary, streams, activeStreamId, initialStream]);

  const handleSelect = (stream: StationStreamRef) => {
    setActiveStreamId(stream.id);
    persistQualityPreference(stream);
    if (currentStation && currentStation.id === baseSummary.id) {
      // Already playing this station: hand the new variant straight to the
      // GlobalPlayer effect, which runs pause-load-play with AbortError
      // handling so the audio swaps without a manual stop.
      setStream(stream);
    }
  };

  return (
    <div className="space-y-4">
      <PlayButton station={summary} color={color} size="lg" streams={streams} />
      <QualitySelector
        streams={streams}
        activeStreamId={activeStreamId ?? ''}
        onSelect={handleSelect}
      />
    </div>
  );
}
