'use client';

import { useEffect, useState } from 'react';
import { Heart } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/users/AuthContext';
import { useToast } from './ToastContext';
import { cn } from '@/lib/utils';

interface HeartButtonProps {
  stationId: string;
  /** Server-provided initial flag; the context's set wins after mount. */
  initialIsFavorite?: boolean | null;
  /** Optional size variant for spacing inside cards vs hero areas. */
  size?: 'sm' | 'md';
  className?: string;
  ariaLabel?: string;
}

export function HeartButton({
  stationId,
  initialIsFavorite,
  size = 'md',
  className,
  ariaLabel,
}: HeartButtonProps) {
  const t = useTranslations('favorites');
  const router = useRouter();
  const { isAuthenticated, favoriteIds, favoritesProvider, setFavoriteFlag } =
    useAuth();
  const { show } = useToast();

  // Track whether this is the *first* toggle for an anonymous user, so we
  // only nag once with the "sign up to sync" CTA per session.
  const [hasShownSignupHint, setHasShownSignupHint] = useState(false);

  // Reconcile with the global set: prefer context state when available.
  const inSet = favoriteIds.has(stationId);
  const [isFav, setIsFav] = useState<boolean>(
    inSet || initialIsFavorite === true,
  );
  useEffect(() => {
    setIsFav(favoriteIds.has(stationId));
  }, [favoriteIds, stationId]);

  async function handleClick(event: React.MouseEvent) {
    event.preventDefault();
    event.stopPropagation();

    const next = !isFav;
    // Optimistic
    setIsFav(next);
    setFavoriteFlag(stationId, next);

    try {
      if (next) await favoritesProvider.add(stationId);
      else await favoritesProvider.remove(stationId);
      // Bust Next.js Server Component cache so SSR data (is_favorite,
      // votes_local) re-fetches on the next render. Without this the
      // page can show stale `is_favorite=false` after a successful add
      // until the per-page revalidate window expires.
      router.refresh();
      if (
        next
        && !isAuthenticated
        && !hasShownSignupHint
      ) {
        show(t('signUpToSync'), { tone: 'info' });
        setHasShownSignupHint(true);
      }
    } catch {
      // Revert optimistic toggle.
      setIsFav(!next);
      setFavoriteFlag(stationId, !next);
      show(t('saveFailed'), { tone: 'error' });
    }
  }

  const sizeClass = size === 'sm' ? 'h-8 w-8' : 'h-10 w-10';
  const icon = size === 'sm' ? 14 : 16;

  return (
    <button
      type="button"
      onClick={handleClick}
      aria-pressed={isFav}
      aria-label={ariaLabel ?? (isFav ? t('remove') : t('add'))}
      className={cn(
        'inline-flex items-center justify-center rounded-full border transition-colors',
        sizeClass,
        isFav
          ? 'border-magenta/60 bg-magenta-soft text-magenta'
          : 'border-fg-3/60 bg-bg-2 text-fg-2 hover:border-magenta hover:text-magenta',
        className,
      )}
    >
      <Heart
        size={icon}
        fill={isFav ? 'currentColor' : 'transparent'}
        strokeWidth={isFav ? 0 : 2}
      />
    </button>
  );
}
