'use client';

import { useEffect, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { Loader2 } from 'lucide-react';
import { Link } from '@/i18n/navigation';
import { useAuth } from '@/lib/users/AuthContext';
import { deleteAccount } from '@/lib/users/auth';
import { useToast } from '@/components/auth/ToastContext';

export default function ProfilePage() {
  const t = useTranslations('auth');
  const tNav = useTranslations('nav');
  const router = useRouter();
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const { show } = useToast();

  const [showDelete, setShowDelete] = useState(false);
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace('/login');
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading || !user) {
    return (
      <div className="text-fg-2 flex items-center justify-center gap-2 py-12 font-mono text-xs uppercase tracking-widest">
        <Loader2 size={16} className="animate-spin" />
        Loading…
      </div>
    );
  }

  async function handleDelete(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await deleteAccount(password);
      show(t('deleted'), { tone: 'info' });
      logout();
      router.replace('/');
    } catch (err) {
      const code = err instanceof Error ? err.message : 'unknown';
      if (code === 'invalid_credentials') setError(t('invalidCredentials'));
      else setError(code);
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-8 py-8">
      <h1 className="font-display text-fg-0 text-3xl font-semibold">
        {tNav('profile')}
      </h1>

      <section className="border-fg-3/40 bg-bg-2/40 space-y-3 rounded-lg border p-5">
        <div>
          <p className="text-fg-2 font-mono text-[10px] uppercase tracking-widest">
            {t('email')}
          </p>
          <p className="text-fg-0 font-mono text-sm">{user.email}</p>
        </div>
        <div>
          <p className="text-fg-2 font-mono text-[10px] uppercase tracking-widest">
            Joined
          </p>
          <p className="text-fg-1 font-mono text-sm">
            {new Date(user.created_at).toLocaleDateString()}
          </p>
        </div>
      </section>

      <section className="border-fg-3/40 bg-bg-2/40 space-y-3 rounded-lg border p-5">
        <h2 className="font-display text-fg-0 text-lg font-semibold">
          {t('deleteAccount')}
        </h2>
        {!showDelete ? (
          <button
            type="button"
            onClick={() => setShowDelete(true)}
            className="border-magenta/40 text-magenta hover:bg-magenta-soft/40 rounded-md border px-3 py-1.5 font-mono text-xs uppercase tracking-widest transition-colors"
          >
            {t('deleteAccount')}
          </button>
        ) : (
          <form onSubmit={handleDelete} className="space-y-3">
            <p className="text-fg-2 text-sm">{t('deleteConfirm')}</p>
            <input
              type="password"
              required
              placeholder={t('password')}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={submitting}
              className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta w-full rounded-md border px-3 py-2 text-sm focus:outline-none disabled:opacity-50"
            />
            {error ? (
              <div className="bg-magenta-soft text-warm rounded-md px-3 py-2 text-sm">
                {error}
              </div>
            ) : null}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  setShowDelete(false);
                  setPassword('');
                  setError(null);
                }}
                disabled={submitting}
                className="border-fg-3 text-fg-1 hover:border-magenta hover:text-fg-0 rounded-md border px-3 py-1.5 font-mono text-xs uppercase tracking-widest transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting || !password}
                className="bg-magenta text-fg-0 inline-flex items-center gap-2 rounded-md px-3 py-1.5 font-display text-sm font-medium transition-colors disabled:opacity-50"
              >
                {submitting ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : null}
                {t('deleteAccount')}
              </button>
            </div>
          </form>
        )}
      </section>

      <p className="text-fg-3 text-center font-mono text-xs">
        <Link href="/support" className="hover:text-fg-1">
          {tNav('support')}
        </Link>
      </p>
    </div>
  );
}
