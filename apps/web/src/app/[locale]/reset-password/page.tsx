'use client';

import { Suspense, useState, type FormEvent } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { Loader2 } from 'lucide-react';
import { Link } from '@/i18n/navigation';
import { resetPassword } from '@/lib/users/auth';

function ResetInner() {
  const t = useTranslations('auth');
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get('token');

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  if (!token) {
    return (
      <div className="mx-auto max-w-sm space-y-3 py-12 text-center">
        <h1 className="font-display text-fg-0 text-2xl font-semibold">
          {t('resetPassword')}
        </h1>
        <p className="text-warm text-sm">{t('tokenMissing')}</p>
        <p className="text-fg-3 font-mono text-xs">
          <Link href="/forgot-password" className="hover:text-fg-0">
            {t('forgotPassword')}
          </Link>
        </p>
      </div>
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    if (password !== confirm) {
      setError(t('passwordsDoNotMatch'));
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await resetPassword(token!, password);
      setDone(true);
      setTimeout(() => router.push('/login?reset=ok'), 1500);
    } catch (err) {
      const code = err instanceof Error ? err.message : 'unknown';
      if (code === 'invalid_or_expired_token') setError(t('tokenInvalid'));
      else if (code === 'invalid_payload') setError(t('passwordTooShort'));
      else setError(code);
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <div className="mx-auto max-w-sm space-y-3 py-12 text-center">
        <h1 className="font-display text-fg-0 text-2xl font-semibold">
          {t('resetPassword')}
        </h1>
        <p className="text-cyan text-sm">{t('passwordUpdated')}</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-sm space-y-6 py-12">
      <h1 className="font-display text-fg-0 text-3xl font-semibold">
        {t('resetPassword')}
      </h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <input
          type="password"
          required
          minLength={8}
          placeholder={t('newPassword')}
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={submitting}
          className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta w-full rounded-md border px-3 py-2 text-sm focus:outline-none disabled:opacity-50"
        />
        <input
          type="password"
          required
          minLength={8}
          placeholder={t('confirmPassword')}
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
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
          disabled={submitting || !password || !confirm}
          className="bg-wave text-fg-0 shadow-sticker hover:bg-magenta hover:shadow-sticker-magenta flex w-full items-center justify-center gap-2 rounded-md py-2.5 font-display text-sm font-medium transition-all disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? <Loader2 size={16} className="animate-spin" /> : null}
          {t('resetPassword')}
        </button>
      </form>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetInner />
    </Suspense>
  );
}
