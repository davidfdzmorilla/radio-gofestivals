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
    <aside className="space-y-5 rounded-xl border border-fg-3 bg-bg-2 p-5">
      <div>
        <label className="block font-mono text-[10px] font-medium uppercase tracking-widest text-fg-2">
          {t('country')}
        </label>
        <select
          value={current.country ?? ''}
          onChange={(e) => updateFilter('country', e.target.value || null)}
          className="mt-1.5 w-full rounded-md border border-fg-3 bg-bg-1 px-3 py-2 text-sm font-medium text-fg-0 transition-colors focus:border-magenta focus:outline-none"
        >
          <option value="">{t('anyCountry')}</option>
          {countries.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>
      <label className="flex cursor-pointer items-center gap-2.5 text-sm font-medium text-fg-1 transition-colors hover:text-fg-0">
        <input
          type="checkbox"
          checked={current.curated ?? false}
          onChange={(e) => updateFilter('curated', e.target.checked ? 'true' : null)}
          className="h-4 w-4 accent-magenta"
        />
        {t('curatedOnly')}
      </label>
    </aside>
  );
}
