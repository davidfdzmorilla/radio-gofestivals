'use client';

import { useTranslations } from 'next-intl';
import { useNowPlaying } from '@/hooks/useNowPlaying';

interface Props {
  slug: string;
  size?: 'sm' | 'lg';
}

export function NowPlaying({ slug, size = 'sm' }: Props) {
  const t = useTranslations('station');
  const { state } = useNowPlaying(slug);

  if (!state || (!state.title && !state.artist)) {
    return (
      <p
        className={
          size === 'lg' ? 'text-lg text-white/60' : 'text-sm text-white/50'
        }
      >
        {t('noMetadata')}
      </p>
    );
  }

  const mainClass =
    size === 'lg' ? 'font-display text-xl text-white' : 'text-sm text-white';
  const subClass =
    size === 'lg' ? 'text-base text-white/70' : 'text-xs text-white/60';

  return (
    <div className="min-w-0">
      <p className={`${mainClass} truncate`}>
        {state.title ?? t('noMetadata')}
      </p>
      {state.artist && <p className={`${subClass} truncate`}>{state.artist}</p>}
    </div>
  );
}
