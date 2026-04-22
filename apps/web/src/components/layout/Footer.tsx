import { getTranslations } from 'next-intl/server';

export async function Footer() {
  const t = await getTranslations('home');
  return (
    <footer className="mt-16 border-t border-white/10 px-4 py-6 text-center text-xs text-white/40">
      <p>© {new Date().getFullYear()} · {t('title')}</p>
    </footer>
  );
}
