'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { useAuth } from '@/lib/users/AuthContext';
import { AuthModal } from './AuthModal';
import { UserMenu } from './UserMenu';

export function HeaderAuth() {
  const t = useTranslations('nav');
  const { isAuthenticated, isLoading, user } = useAuth();
  const [showModal, setShowModal] = useState(false);

  if (isLoading) {
    return (
      <span
        aria-hidden
        className="bg-bg-3/40 inline-block h-6 w-16 animate-pulse rounded-md"
      />
    );
  }

  if (isAuthenticated && user) {
    return <UserMenu user={user} />;
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setShowModal(true)}
        className="border-fg-3 text-fg-1 hover:border-magenta hover:text-fg-0 rounded-md border px-3 py-1.5 font-mono text-xs uppercase tracking-widest transition-colors"
      >
        {t('signin')}
      </button>
      {showModal ? (
        <AuthModal onClose={() => setShowModal(false)} />
      ) : null}
    </>
  );
}
