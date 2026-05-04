'use client';

import { useEffect, useRef, useState } from 'react';
import { Heart, LogOut, User as UserIcon } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';
import { Link } from '@/i18n/navigation';
import { useAuth } from '@/lib/users/AuthContext';
import type { User } from '@/lib/users/types';
import { cn } from '@/lib/utils';

interface UserMenuProps {
  user: User;
}

export function UserMenu({ user }: UserMenuProps) {
  const t = useTranslations('nav');
  const router = useRouter();
  const { logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const escHandler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    document.addEventListener('keydown', escHandler);
    return () => {
      document.removeEventListener('mousedown', handler);
      document.removeEventListener('keydown', escHandler);
    };
  }, [open]);

  const initial = user.email.charAt(0).toUpperCase();

  function handleLogout() {
    logout();
    setOpen(false);
    router.push('/');
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={user.email}
        className="bg-magenta-soft text-magenta hover:bg-magenta hover:text-fg-0 inline-flex h-9 w-9 items-center justify-center rounded-full font-display text-sm font-bold transition-colors"
      >
        {initial}
      </button>

      {open ? (
        <div
          role="menu"
          className={cn(
            'border-fg-3/40 bg-bg-2 fixed inset-x-4 bottom-4 z-50 rounded-lg border p-2 shadow-sticker-lg',
            'sm:absolute sm:inset-auto sm:right-0 sm:top-12 sm:w-56 sm:p-1',
          )}
        >
          <div className="border-fg-3/30 mb-1 border-b px-3 py-2">
            <p className="text-fg-2 font-mono text-[10px] uppercase tracking-widest">
              {user.email}
            </p>
          </div>
          <Link
            href="/profile"
            onClick={() => setOpen(false)}
            className="hover:bg-bg-3 text-fg-1 hover:text-fg-0 flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors"
          >
            <UserIcon size={14} />
            {t('profile')}
          </Link>
          <Link
            href="/favorites"
            onClick={() => setOpen(false)}
            className="hover:bg-bg-3 text-fg-1 hover:text-fg-0 flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors"
          >
            <Heart size={14} />
            {t('favorites')}
          </Link>
          <button
            type="button"
            onClick={handleLogout}
            className="text-warm hover:bg-magenta-soft/40 flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors"
          >
            <LogOut size={14} />
            {t('logout')}
          </button>
        </div>
      ) : null}
    </div>
  );
}
