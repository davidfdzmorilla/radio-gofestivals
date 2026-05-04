'use client';

import { Suspense, useEffect, useState, type FormEvent } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { Loader2 } from 'lucide-react';
import { Link } from '@/i18n/navigation';
import { useAuth } from '@/lib/users/AuthContext';
import { loginUser } from '@/lib/users/auth';
import { useToast } from '@/components/auth/ToastContext';

function LoginInner() {
  const t = useTranslations('auth');
  const tFav = useTranslations('favorites');
  const router = useRouter();
  const params = useSearchParams();
  const returnTo = params.get('return_url') ?? '/';

  const { login, isAuthenticated, isLoading } = useAuth();
  const { show } = useToast();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace(returnTo);
    }
  }, [isAuthenticated, isLoading, returnTo, router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const auth = await loginUser(email, password);
      const { migrated } = await login(auth.access_token, auth.user);
      if (migrated > 0) {
        show(tFav('syncedToast', { count: migrated }), { tone: 'success' });
      }
      router.replace(returnTo);
    } catch (err) {
      const code = err instanceof Error ? err.message : 'unknown';
      if (code === 'invalid_credentials') setError(t('invalidCredentials'));
      else if (code === 'rate_limit_exceeded') setError(t('rateLimited'));
      else setError(code);
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm space-y-6 py-12">
      <h1 className="font-display text-fg-0 text-3xl font-semibold">
        {t('signIn')}
      </h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field label={t('email')} htmlFor="email">
          <input
            id="email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={submitting}
            className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta w-full rounded-md border px-3 py-2 text-sm focus:outline-none disabled:opacity-50"
          />
        </Field>
        <Field label={t('password')} htmlFor="password">
          <input
            id="password"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={submitting}
            className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta w-full rounded-md border px-3 py-2 text-sm focus:outline-none disabled:opacity-50"
          />
        </Field>
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
          disabled={submitting || !email || !password}
          className="bg-wave text-fg-0 shadow-sticker hover:bg-magenta hover:shadow-sticker-magenta flex w-full items-center justify-center gap-2 rounded-md py-2.5 font-display text-sm font-medium transition-all disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? <Loader2 size={16} className="animate-spin" /> : null}
          {t('signIn')}
        </button>
      </form>
      <div className="flex items-center justify-between font-mono text-xs text-fg-2">
        <Link href="/forgot-password" className="hover:text-fg-0">
          {t('forgotPassword')}
        </Link>
        <Link href="/signup" className="hover:text-fg-0">
          {t('needAccount')}
        </Link>
      </div>
    </div>
  );
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label
        htmlFor={htmlFor}
        className="text-fg-2 block font-mono text-[10px] uppercase tracking-widest"
      >
        {label}
      </label>
      {children}
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginInner />
    </Suspense>
  );
}
