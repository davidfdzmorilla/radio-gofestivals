import { getTranslations } from 'next-intl/server';
import { Link } from '@/i18n/navigation';
import { Button } from '@/components/ui/button';

export default async function NotFound() {
  const t = await getTranslations('station');
  const tCommon = await getTranslations('common');
  return (
    <div className="mx-auto flex min-h-[55vh] max-w-md flex-col items-center justify-center gap-5 text-center">
      <span
        aria-hidden
        className="inline-flex h-16 w-16 rotate-1 items-center justify-center rounded-full bg-wave-soft font-display text-3xl font-bold text-wave shadow-sticker"
      >
        ?
      </span>
      <h1 className="font-display text-3xl font-semibold text-fg-0">
        {t('notFound')}
      </h1>
      <Link href="/">
        <Button>{tCommon('back')}</Button>
      </Link>
    </div>
  );
}
