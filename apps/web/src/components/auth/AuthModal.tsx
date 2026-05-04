'use client';

import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { Eye, EyeOff, Loader2, X } from 'lucide-react';
import { useAuth } from '@/lib/users/AuthContext';
import { loginUser, registerUser } from '@/lib/users/auth';
import { Modal } from '@/components/ui/Modal';
import { useToast } from './ToastContext';
import { cn } from '@/lib/utils';

export type AuthModalTab = 'signin' | 'signup';

interface AuthModalProps {
  initialTab?: AuthModalTab;
  /** Optional contextual headline (e.g. "Sign in to vote"). */
  prompt?: string;
  onClose: () => void;
}

export function AuthModal({
  initialTab = 'signin',
  prompt,
  onClose,
}: AuthModalProps) {
  const t = useTranslations('auth');
  const tFav = useTranslations('favorites');
  const router = useRouter();
  const { login } = useAuth();
  const { show } = useToast();

  const [tab, setTab] = useState<AuthModalTab>(initialTab);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ESC + body-scroll lock + backdrop click are handled by <Modal />.

  function mapErrorToMessage(code: string): string {
    if (code === 'invalid_credentials') return t('invalidCredentials');
    if (code === 'email_already_exists') return t('emailExists');
    if (code === 'rate_limit_exceeded') return t('rateLimited');
    if (code === 'invalid_payload') return t('passwordTooShort');
    return code;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    setError(null);

    if (tab === 'signup' && password !== confirmPassword) {
      setError(t('passwordsDoNotMatch'));
      return;
    }

    setSubmitting(true);
    try {
      const auth =
        tab === 'signup'
          ? await registerUser(email, password)
          : await loginUser(email, password);
      const { migrated } = await login(auth.access_token, auth.user);
      if (migrated > 0) {
        show(tFav('syncedToast', { count: migrated }), {
          tone: 'success',
        });
      }
      onClose();
    } catch (err) {
      const code = err instanceof Error ? err.message : 'unknown';
      setError(mapErrorToMessage(code));
      setSubmitting(false);
    }
  }

  return (
    <Modal isOpen onClose={onClose} dismissable={!submitting} panelClassName="p-6">
      <div className="flex flex-col gap-5">
        <div className="flex items-start justify-between">
          <h2 className="font-display text-fg-0 text-xl font-semibold">
            {tab === 'signin' ? t('signIn') : t('signUp')}
          </h2>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            aria-label="Close"
            className="text-fg-2 hover:text-fg-0 disabled:opacity-50"
          >
            <X size={18} />
          </button>
        </div>

        {prompt ? (
          <p className="text-fg-2 text-sm">{prompt}</p>
        ) : null}

        <div className="border-fg-3/40 flex gap-1 rounded-md border p-1 text-xs">
          <button
            type="button"
            onClick={() => setTab('signin')}
            className={cn(
              'flex-1 rounded-sm py-1.5 font-mono uppercase tracking-widest transition-colors',
              tab === 'signin'
                ? 'bg-bg-3 text-fg-0'
                : 'text-fg-2 hover:text-fg-0',
            )}
          >
            {t('signIn')}
          </button>
          <button
            type="button"
            onClick={() => setTab('signup')}
            className={cn(
              'flex-1 rounded-sm py-1.5 font-mono uppercase tracking-widest transition-colors',
              tab === 'signup'
                ? 'bg-bg-3 text-fg-0'
                : 'text-fg-2 hover:text-fg-0',
            )}
          >
            {t('signUp')}
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label
              htmlFor="auth-email"
              className="text-fg-2 block font-mono text-[10px] uppercase tracking-widest"
            >
              {t('email')}
            </label>
            <input
              id="auth-email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={submitting}
              className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta w-full rounded-md border px-3 py-2 text-sm focus:outline-none disabled:opacity-50"
            />
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="auth-password"
              className="text-fg-2 block font-mono text-[10px] uppercase tracking-widest"
            >
              {t('password')}
            </label>
            <div className="relative">
              <input
                id="auth-password"
                type={showPassword ? 'text' : 'password'}
                required
                minLength={tab === 'signup' ? 8 : 1}
                autoComplete={
                  tab === 'signup' ? 'new-password' : 'current-password'
                }
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={submitting}
                className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta w-full rounded-md border px-3 py-2 pr-10 text-sm focus:outline-none disabled:opacity-50"
              />
              <button
                type="button"
                tabIndex={-1}
                onClick={() => setShowPassword((v) => !v)}
                aria-label={
                  showPassword ? 'Hide password' : 'Show password'
                }
                className="text-fg-2 hover:text-fg-0 absolute right-2 top-1/2 -translate-y-1/2"
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {tab === 'signup' ? (
            <div className="space-y-1.5">
              <label
                htmlFor="auth-confirm"
                className="text-fg-2 block font-mono text-[10px] uppercase tracking-widest"
              >
                {t('confirmPassword')}
              </label>
              <input
                id="auth-confirm"
                type={showPassword ? 'text' : 'password'}
                required
                minLength={8}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                disabled={submitting}
                className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta w-full rounded-md border px-3 py-2 text-sm focus:outline-none disabled:opacity-50"
              />
            </div>
          ) : null}

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
            {tab === 'signin' ? t('signIn') : t('signUp')}
          </button>
        </form>

        <div className="text-fg-2 flex items-center justify-between text-xs">
          {tab === 'signin' ? (
            <Link
              href="/forgot-password"
              onClick={onClose}
              className="hover:text-fg-0 transition-colors"
            >
              {t('forgotPassword')}
            </Link>
          ) : (
            <span />
          )}
          <button
            type="button"
            onClick={() =>
              setTab(tab === 'signin' ? 'signup' : 'signin')
            }
            className="hover:text-fg-0 transition-colors"
          >
            {tab === 'signin' ? t('needAccount') : t('haveAccount')}
          </button>
        </div>
      </div>
    </Modal>
  );
}
