'use client';

import { useTranslations } from 'next-intl';
import { useRouter, usePathname } from '@/i18n/navigation';
import type { Route } from 'next';

interface Props {
  current: { country?: string; curated?: boolean };
  countries: string[];
}

export function SidebarFilters({ current, countries }: Props) {
  const t = useTranslations('filters');
  const router = useRouter();
  const pathname = usePathname();

  const updateFilter = (key: 'country' | 'curated', value: string | null) => {
    const url = new URL(window.location.href);
    if (value === null || value === '') url.searchParams.delete(key);
    else url.searchParams.set(key, value);
    url.searchParams.delete('page');
    router.replace(
      (pathname + (url.searchParams.toString() ? `?${url.searchParams}` : '')) as unknown as Route,
    );
  };

  return (
    <aside className="space-y-4 rounded-lg border border-white/10 bg-white/5 p-4">
      <div>
        <label className="block text-xs font-medium uppercase tracking-wide text-white/50">
          {t('country')}
        </label>
        <select
          value={current.country ?? ''}
          onChange={(e) => updateFilter('country', e.target.value || null)}
          className="mt-1 w-full rounded-md border border-white/10 bg-ink px-3 py-2 text-sm text-white focus:border-wave focus:outline-none"
        >
          <option value="">{t('anyCountry')}</option>
          {countries.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>
      <label className="flex cursor-pointer items-center gap-2 text-sm text-white/80">
        <input
          type="checkbox"
          checked={current.curated ?? false}
          onChange={(e) => updateFilter('curated', e.target.checked ? 'true' : null)}
          className="h-4 w-4 accent-wave"
        />
        {t('curatedOnly')}
      </label>
    </aside>
  );
}
