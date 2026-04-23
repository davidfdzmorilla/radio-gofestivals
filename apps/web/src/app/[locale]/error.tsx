'use client';

import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';

export default function Error({ reset }: { error: Error; reset: () => void }) {
  const t = useTranslations('common');
  return (
    <div className="mx-auto flex min-h-[55vh] max-w-md flex-col items-center justify-center gap-5 text-center">
      <span
        aria-hidden
        className="inline-flex h-16 w-16 -rotate-1 items-center justify-center rounded-full bg-magenta-soft font-display text-3xl font-bold text-magenta shadow-sticker-magenta"
      >
        ✕
      </span>
      <div className="space-y-2">
        <h1 className="font-display text-3xl font-semibold text-fg-0">
          {t('error')}
        </h1>
        <p className="text-fg-2">{t('errorSubtitle')}</p>
      </div>
      <Button variant="magenta" onClick={reset}>
        {t('retry')}
      </Button>
    </div>
  );
}
