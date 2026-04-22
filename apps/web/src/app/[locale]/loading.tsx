import { getTranslations } from 'next-intl/server';

export default async function Loading() {
  const t = await getTranslations('common');
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <p className="font-mono text-sm text-white/40">{t('loading')}</p>
    </div>
  );
}
