'use client';

import { useEffect, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { Eye, EyeOff, Loader2 } from 'lucide-react';
import { isAuthenticated, login, LoginError } from '@/lib/admin/auth';

export default function AdminLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isAuthenticated()) {
      router.replace('/admin');
    }
  }, [router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      await login(email, password);
      router.push('/admin');
    } catch (err) {
      const code = err instanceof LoginError ? err.code : 'unknown';
      if (code === 'invalid_credentials') {
        setError('Email o contraseña incorrectos');
      } else if (code === 'rate_limit_exceeded') {
        setError('Demasiados intentos, espera 1 minuto');
      } else {
        setError('Error de conexión, inténtalo de nuevo');
      }
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <form
        onSubmit={handleSubmit}
        className="border-fg-3/40 bg-bg-2/60 w-full max-w-sm space-y-5 rounded-lg border p-8 shadow-sticker"
      >
        <div className="space-y-1 text-center">
          <h1 className="font-display text-fg-0 text-2xl font-semibold">
            Admin Login
          </h1>
          <p className="text-fg-2 font-mono text-[11px] uppercase tracking-widest">
            radio.gofestivals
          </p>
        </div>

        <div className="space-y-1.5">
          <label
            htmlFor="email"
            className="text-fg-2 font-mono text-[10px] uppercase tracking-widest"
          >
            Email
          </label>
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
        </div>

        <div className="space-y-1.5">
          <label
            htmlFor="password"
            className="text-fg-2 font-mono text-[10px] uppercase tracking-widest"
          >
            Password
          </label>
          <div className="relative">
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={submitting}
              className="border-fg-3 bg-bg-1 text-fg-0 focus:border-magenta w-full rounded-md border px-3 py-2 pr-10 text-sm focus:outline-none disabled:opacity-50"
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              tabIndex={-1}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
              className="text-fg-2 hover:text-fg-0 absolute right-2 top-1/2 -translate-y-1/2 transition-colors"
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </div>

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
          {submitting ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              Verificando…
            </>
          ) : (
            'Sign in'
          )}
        </button>
      </form>
    </div>
  );
}
