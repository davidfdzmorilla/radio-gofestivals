'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { Loader2 } from 'lucide-react';
import { Link } from '@/i18n/navigation';
import { verifyEmail } from '@/lib/users/auth';

type Status = 'verifying' | 'done' | 'error';

function VerifyInner() {
  const t = useTranslations('auth');
  const params = useSearchParams();
  const token = params.get('token');
  const [status, setStatus] = useState<Status>('verifying');

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    verifyEmail(token)
      .then(() => {
        if (!cancelled) setStatus('done');
      })
      .catch(() => {
        if (!cancelled) setStatus('error');
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <div className="mx-auto max-w-sm space-y-3 py-12 text-center">
      <h1 className="font-display text-fg-0 text-2xl font-semibold">
        {t('verifyEmailTitle')}
      </h1>
      {!token && <p className="text-warm text-sm">{t('tokenMissing')}</p>}
      {token && status === 'verifying' && (
        <p className="text-fg-2 flex items-center justify-center gap-2 text-sm">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          {t('verifyEmailVerifying')}
        </p>
      )}
      {token && status === 'done' && (
        <>
          <p className="text-fg-1 text-sm">{t('verifyEmailDone')}</p>
          <p className="text-fg-3 font-mono text-xs">
            <Link href="/" className="hover:text-fg-0">
              {t('backToHome')}
            </Link>
          </p>
        </>
      )}
      {token && status === 'error' && (
        <p className="text-warm text-sm">{t('verifyEmailError')}</p>
      )}
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={null}>
      <VerifyInner />
    </Suspense>
  );
}
