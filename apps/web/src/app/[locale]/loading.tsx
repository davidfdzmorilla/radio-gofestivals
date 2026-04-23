import { getTranslations } from 'next-intl/server';

export default async function Loading() {
  const t = await getTranslations('common');
  return (
    <div className="space-y-8">
      <div className="skeleton h-12 w-2/3 rounded-xl" />
      <div className="skeleton h-6 w-1/3 rounded-lg" />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="skeleton h-24 rounded-xl" />
        ))}
      </div>
      <p className="sr-only">{t('loading')}</p>
    </div>
  );
}
