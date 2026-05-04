import { getTranslations } from 'next-intl/server';
import { ExternalLink } from 'lucide-react';

const ISSUES_URL =
  'https://github.com/davidfdzmorilla/radio-gofestivals/issues';

export default async function SupportPage() {
  const t = await getTranslations('auth');
  return (
    <div className="mx-auto max-w-xl space-y-6 py-8">
      <h1 className="font-display text-fg-0 text-3xl font-semibold">
        {t('support')}
      </h1>
      <p className="text-fg-2 text-sm">
        radio.gofestivals is built and run by one human. The fastest way to
        get help — bugs, account issues, or feedback — is to open a ticket
        on GitHub.
      </p>
      <a
        href={ISSUES_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="bg-wave text-fg-0 shadow-sticker hover:bg-magenta hover:shadow-sticker-magenta inline-flex items-center gap-2 rounded-md px-3 py-2 font-display text-sm font-medium transition-all"
      >
        Open a GitHub issue <ExternalLink size={14} />
      </a>
    </div>
  );
}
