'use client';

import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { Heart, LogOut, Menu, User as UserIcon, X } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';
import { Link } from '@/i18n/navigation';
import { useAuth } from '@/lib/users/AuthContext';
import { LocaleSwitcher } from '@/components/layout/LocaleSwitcher';
import { AuthModal } from './AuthModal';
import { cn } from '@/lib/utils';

export function MobileMenu() {
  const t = useTranslations('nav');
  const router = useRouter();
  const { isAuthenticated, isLoading, user, logout } = useAuth();

  const [open, setOpen] = useState(false);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', handler);
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', handler);
      document.body.style.overflow = '';
    };
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open menu"
        className="text-fg-1 hover:text-fg-0 inline-flex h-9 w-9 items-center justify-center rounded-md md:hidden"
      >
        <Menu size={20} />
      </button>

      {open && mounted ? createPortal(
        <div className="fixed inset-0 z-50 md:hidden">
          {/* Plain backdrop without backdrop-blur — the filter was
              leaking into the sibling drawer's rendering, washing out
              its background. */}
          <div
            aria-hidden
            className="bg-black/70 absolute inset-0"
            onClick={() => setOpen(false)}
          />
          <div
            className={cn(
              "bg-bg-2",
              'bg-bg-1 border-fg-3/40 absolute right-0 top-0 flex h-full w-72 max-w-full flex-col border-l p-6 shadow-sticker-lg',
            )}
          >
            <div className="mb-6 flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-widest text-fg-2">
                Menu
              </span>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close menu"
                className="text-fg-2 hover:text-fg-0"
              >
                <X size={20} />
              </button>
            </div>

            <nav className="flex flex-col gap-1">
              <Link
                href="/"
                onClick={() => setOpen(false)}
                className="text-fg-1 hover:bg-bg-3 hover:text-fg-0 rounded-md px-3 py-2 text-sm transition-colors"
              >
                {t('home')}
              </Link>
              <Link
                href="/genres"
                onClick={() => setOpen(false)}
                className="text-fg-1 hover:bg-bg-3 hover:text-fg-0 rounded-md px-3 py-2 text-sm transition-colors"
              >
                {t('genres')}
              </Link>
              <Link
                href="/favorites"
                onClick={() => setOpen(false)}
                className="text-fg-1 hover:bg-bg-3 hover:text-fg-0 flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors"
              >
                <Heart size={14} />
                {t('favorites')}
              </Link>
            </nav>

            <div className="border-fg-3/30 my-6 border-t" />

            <div className="mb-4">
              <LocaleSwitcher />
            </div>

            <div className="border-fg-3/30 mt-auto border-t pt-4">
              {isLoading ? (
                <span className="bg-bg-3/40 inline-block h-9 w-24 animate-pulse rounded-md" />
              ) : isAuthenticated && user ? (
                <div className="space-y-2">
                  <p className="text-fg-2 font-mono text-[10px] uppercase tracking-widest">
                    {user.email}
                  </p>
                  <Link
                    href="/profile"
                    onClick={() => setOpen(false)}
                    className="text-fg-1 hover:bg-bg-3 hover:text-fg-0 flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors"
                  >
                    <UserIcon size={14} />
                    {t('profile')}
                  </Link>
                  <button
                    type="button"
                    onClick={() => {
                      logout();
                      setOpen(false);
                      router.push('/');
                    }}
                    className="text-warm hover:bg-magenta-soft/40 flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors"
                  >
                    <LogOut size={14} />
                    {t('logout')}
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    setShowAuthModal(true);
                    setOpen(false);
                  }}
                  className="bg-wave text-fg-0 shadow-sticker hover:bg-magenta hover:shadow-sticker-magenta inline-flex w-full items-center justify-center gap-2 rounded-md px-3 py-2 font-display text-sm font-medium transition-all"
                >
                  {t('signin')}
                </button>
              )}
            </div>
          </div>
        </div>,
        document.body,
      ) : null}

      {showAuthModal ? (
        <AuthModal onClose={() => setShowAuthModal(false)} />
      ) : null}
    </>
  );
}
