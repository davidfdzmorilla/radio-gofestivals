import { getTranslations } from 'next-intl/server';
import { Link } from '@/i18n/navigation';
import { Button } from '@/components/ui/button';

export default async function NotFound() {
  const t = await getTranslations('station');
  const tCommon = await getTranslations('common');
  return (
    <div className="mx-auto flex min-h-[50vh] max-w-md flex-col items-center justify-center gap-4 text-center">
      <h1 className="font-display text-2xl text-white">{t('notFound')}</h1>
      <Link href="/">
        <Button>{tCommon('back')}</Button>
      </Link>
    </div>
  );
}
