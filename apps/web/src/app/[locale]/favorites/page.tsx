'use client';

import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import { Heart, Loader2 } from 'lucide-react';
import { Link } from '@/i18n/navigation';
import { useAuth } from '@/lib/users/AuthContext';
import { HeartButton } from '@/components/auth/HeartButton';
import { Badge } from '@/components/ui/badge';
import { initials } from '@/lib/utils';
import type { FavoriteOut } from '@/lib/users/types';

export default function FavoritesPage() {
  const t = useTranslations('favorites');
  const tNav = useTranslations('nav');
  const { isAuthenticated, isLoading, favoritesProvider, favoriteIds } =
    useAuth();

  const [items, setItems] = useState<FavoriteOut[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (isLoading) return;
    let cancelled = false;
    setLoading(true);
    favoritesProvider
      .list()
      .then((list) => {
        if (!cancelled) setItems(list);
      })
      .catch(() => {
        if (!cancelled) setItems([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [favoritesProvider, isLoading, favoriteIds]);

  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between gap-4">
        <h1 className="font-display text-fg-0 text-3xl font-semibold">
          {t('title')}
        </h1>
        {!isAuthenticated && items.length > 0 ? (
          <Link
            href="/signup"
            className="border-fg-3 text-fg-1 hover:border-magenta hover:text-fg-0 rounded-md border px-3 py-1.5 font-mono text-xs uppercase tracking-widest transition-colors"
          >
            {t('signUpToSync')}
          </Link>
        ) : null}
      </div>

      {loading ? (
        <div className="text-fg-2 flex items-center justify-center gap-2 py-12 font-mono text-xs uppercase tracking-widest">
          <Loader2 size={16} className="animate-spin" />
          Loading…
        </div>
      ) : items.length === 0 ? (
        <div className="border-fg-3/40 bg-bg-2/40 space-y-3 rounded-lg border p-8 text-center">
          <Heart className="text-fg-3 mx-auto" size={32} />
          <p className="text-fg-2 text-sm">{t('empty')}</p>
          {!isAuthenticated ? (
            <p className="text-fg-3 text-xs">
              <Link
                href="/signup"
                className="text-magenta hover:text-warm"
              >
                {t('signUpToSync')}
              </Link>
            </p>
          ) : null}
          <p className="text-fg-3 text-xs">
            <Link href="/" className="hover:text-fg-1">
              ← {tNav('home')}
            </Link>
          </p>
        </div>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {items.map((fav) => (
            <li
              key={fav.station_id}
              className="border-fg-3/40 bg-bg-2/40 hover:bg-bg-3/40 flex items-center gap-3 rounded-lg border p-4 transition-colors"
            >
              <div
                className="bg-wave text-bg-0 flex h-12 w-12 shrink-0 items-center justify-center rounded-md font-display text-sm font-bold"
              >
                {initials(fav.name)}
              </div>
              <div className="min-w-0 flex-1">
                <Link
                  href={`/stations/${fav.slug}`}
                  className="text-fg-0 hover:text-magenta block truncate font-medium transition-colors"
                >
                  {fav.name}
                </Link>
                <p className="text-fg-2 truncate font-mono text-[11px] uppercase tracking-widest">
                  {fav.country_code ?? '—'}
                  {fav.curated ? (
                    <Badge tone="magenta" sticker className="ml-2">
                      Curated
                    </Badge>
                  ) : null}
                </p>
              </div>
              <HeartButton
                stationId={fav.station_id}
                initialIsFavorite
                size="sm"
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
