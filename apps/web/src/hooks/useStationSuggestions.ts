'use client';

import { useEffect, useState } from 'react';
import { suggestStations } from '@/lib/api';
import type { StationSuggestion } from '@/lib/types';
import { useDebouncedValue } from './useDebounce';

const MIN_QUERY_LENGTH = 2;
const SUGGESTION_LIMIT = 8;

export function useStationSuggestions(query: string): {
  suggestions: StationSuggestion[];
  loading: boolean;
} {
  const debounced = useDebouncedValue(query, 300);
  const [suggestions, setSuggestions] = useState<StationSuggestion[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const q = debounced.trim();
    if (q.length < MIN_QUERY_LENGTH) {
      setSuggestions([]);
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    suggestStations(q, { limit: SUGGESTION_LIMIT, signal: controller.signal })
      .then((items) => {
        setSuggestions(items);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        // Un typeahead nunca debe romper el header: degradar a vacío.
        setSuggestions([]);
        setLoading(false);
      });
    return () => controller.abort();
  }, [debounced]);

  return { suggestions, loading };
}
