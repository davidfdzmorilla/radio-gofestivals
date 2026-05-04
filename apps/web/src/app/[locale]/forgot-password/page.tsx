'use client';

import { useState, type FormEvent } from 'react';
import { useTranslations } from 'next-intl';
import { Loader2 } from 'lucide-react';
import { Link } from '@/i18n/navigation';
import { forgotPassword } from '@/lib/users/auth';

export default function ForgotPasswordPage() {
  const t = useTranslations('auth');

  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await forgotPassword(email);
      setSubmitted(true);
    } catch (err) {
      const code = err instanceof Error ? err.message : 'unknown';
      if (code === 'rate_limit_exceeded') setError(t('rateLimited'));
      else setError(code);
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <div className="mx-auto max-w-sm space-y-4 py-12 text-center">
        <h1 className="font-display text-fg-0 text-2xl font-semibold">
          {t('forgotPassword')}
        </h1>
        <p className="text-fg-2 text-sm">{t('resetEmailSent')}</p>
        <p className="text-fg-3 font-mono text-xs">
          <Link href="/login" className="hover:text-fg-0">
            {t('signIn')}
          </Link>
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-sm space-y-6 py-12">
      <h1 className="font-display text-fg-0 text-3xl font-semibold">
        {t('forgotPassword')}
      </h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <input
          type="email"
          required
          placeholder={t('email')}
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={submitting}
          className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta w-full rounded-md border px-3 py-2 text-sm focus:outline-none disabled:opacity-50"
        />
        {error ? (
          <div
            role="alert"
            className="bg-magenta-soft text-warm rounded-md px-3 py-2 text-sm"
          >
            {error}
          </div>
        ) : null}
        <button
          type="submit"
          disabled={submitting || !email}
          className="bg-wave text-fg-0 shadow-sticker hover:bg-magenta hover:shadow-sticker-magenta flex w-full items-center justify-center gap-2 rounded-md py-2.5 font-display text-sm font-medium transition-all disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? <Loader2 size={16} className="animate-spin" /> : null}
          {t('sendResetLink')}
        </button>
      </form>
      <p className="text-fg-2 text-center font-mono text-xs">
        <Link href="/login" className="hover:text-fg-0">
          {t('signIn')}
        </Link>
      </p>
    </div>
  );
}
