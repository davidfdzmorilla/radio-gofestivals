import { getTranslations } from 'next-intl/server';

export async function Footer() {
  const t = await getTranslations('home');
  return (
    <footer className="mt-20 border-t border-fg-3/30 px-4 py-8">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-2 text-center sm:flex-row sm:justify-between">
        <p className="font-display text-sm font-medium text-fg-1">
          <span className="mr-2 inline-block h-2 w-2 -translate-y-0.5 rounded-full bg-magenta align-middle" />
          {t('title')}
        </p>
        <p className="font-mono text-[11px] uppercase tracking-widest text-fg-2">
          © {new Date().getFullYear()} · {t('tagline')}
        </p>
      </div>
    </footer>
  );
}
