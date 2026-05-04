'use client';

import { useState } from 'react';
import { ThumbsUp } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/users/AuthContext';
import { likeStation, unlikeStation } from '@/lib/users/votes';
import { AuthModal } from './AuthModal';
import { useToast } from './ToastContext';
import { cn } from '@/lib/utils';

interface LikeButtonProps {
  stationId: string;
  initialUserVoted?: boolean | null;
  initialVotesLocal?: number;
  size?: 'sm' | 'md';
  className?: string;
}

export function LikeButton({
  stationId,
  initialUserVoted,
  initialVotesLocal = 0,
  size = 'md',
  className,
}: LikeButtonProps) {
  const t = useTranslations('vote');
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const { show } = useToast();

  const [voted, setVoted] = useState<boolean>(
    initialUserVoted === true,
  );
  const [count, setCount] = useState<number>(initialVotesLocal ?? 0);
  const [showAuthPrompt, setShowAuthPrompt] = useState(false);
  const [busy, setBusy] = useState(false);

  async function handleClick(event: React.MouseEvent) {
    event.preventDefault();
    event.stopPropagation();
    if (busy) return;

    if (!isAuthenticated) {
      setShowAuthPrompt(true);
      return;
    }

    const next = !voted;
    // Optimistic
    setVoted(next);
    setCount((c) => Math.max(0, c + (next ? 1 : -1)));
    setBusy(true);
    try {
      const fn = next ? likeStation : unlikeStation;
      const result = await fn(stationId);
      // Reconcile with server count (in case other users voted concurrently).
      setVoted(result.user_voted);
      setCount(result.votes_local);
      // Bust Next.js Server Component cache so reloads see fresh
      // votes_local instead of the cached SSR snapshot.
      router.refresh();
    } catch {
      // Revert
      setVoted(!next);
      setCount((c) => Math.max(0, c + (next ? -1 : 1)));
      show('Vote failed', { tone: 'error' });
    } finally {
      setBusy(false);
    }
  }

  const sizeClass = size === 'sm' ? 'h-8 px-2 text-[11px]' : 'h-9 px-3';
  const icon = size === 'sm' ? 13 : 16;

  return (
    <>
      <button
        type="button"
        onClick={handleClick}
        aria-pressed={voted}
        aria-label={voted ? t('voted') : t('vote')}
        className={cn(
          'inline-flex items-center gap-1.5 rounded-full border font-mono text-xs transition-colors',
          sizeClass,
          voted
            ? 'border-cyan/40 bg-cyan-soft/60 text-cyan'
            : 'border-fg-3/60 bg-bg-2 text-fg-2 hover:border-cyan hover:text-cyan',
          className,
        )}
      >
        <ThumbsUp
          size={icon}
          fill={voted ? 'currentColor' : 'transparent'}
          strokeWidth={voted ? 0 : 2}
        />
        <span className="tabular-nums">{count}</span>
      </button>
      {showAuthPrompt ? (
        <AuthModal
          initialTab="signin"
          prompt={t('signInToVote')}
          onClose={() => setShowAuthPrompt(false)}
        />
      ) : null}
    </>
  );
}
