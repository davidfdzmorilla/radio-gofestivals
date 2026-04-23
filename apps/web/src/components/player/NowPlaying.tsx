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
          size === 'lg'
            ? 'font-display text-lg italic text-fg-2'
            : 'text-xs italic text-fg-2'
        }
      >
        {t('noMetadata')}
      </p>
    );
  }

  const key = `${state.title ?? ''}|${state.artist ?? ''}`;
  const mainClass =
    size === 'lg'
      ? 'font-display text-2xl font-semibold text-fg-0'
      : 'text-sm font-medium text-fg-0';
  const subClass =
    size === 'lg'
      ? 'mt-1 font-mono text-sm uppercase tracking-wide text-warm'
      : 'font-mono text-[11px] uppercase tracking-wide text-warm';

  return (
    <div key={key} className="min-w-0 animate-np">
      <p className={`${mainClass} truncate`}>
        {state.title ?? t('noMetadata')}
      </p>
      {state.artist && <p className={`${subClass} truncate`}>{state.artist}</p>}
    </div>
  );
}
