'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  type AdminMe,
  getMe,
  isAuthenticated,
  logout,
} from '@/lib/admin/auth';
import { cn } from '@/lib/utils';
import '../globals.css';

const NAV_ITEMS = [
  { href: '/admin', label: 'Dashboard' },
  { href: '/admin/stations', label: 'Stations' },
  { href: '/admin/genres', label: 'Genres' },
  { href: '/admin/operations', label: 'Operations' },
];

function isActive(pathname: string, href: string): boolean {
  if (href === '/admin') return pathname === '/admin';
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [me, setMe] = useState<AdminMe | null>(null);
  const [checking, setChecking] = useState(true);

  const isLoginPage = pathname === '/admin/login';

  useEffect(() => {
    if (isLoginPage) {
      setChecking(false);
      return;
    }

    if (!isAuthenticated()) {
      router.replace('/admin/login');
      return;
    }

    let cancelled = false;
    getMe()
      .then((data) => {
        if (!cancelled) {
          setMe(data);
          setChecking(false);
        }
      })
      .catch(() => {
        if (!cancelled) logout();
      });

    return () => {
      cancelled = true;
    };
  }, [pathname, isLoginPage, router]);

  if (isLoginPage) {
    return <div className="bg-bg-1 text-fg-1 min-h-screen">{children}</div>;
  }

  if (checking || !me) {
    return (
      <div className="bg-bg-1 text-fg-2 flex min-h-screen items-center justify-center font-mono text-xs uppercase tracking-widest">
        Verifying…
      </div>
    );
  }

  return (
    <div className="bg-bg-1 text-fg-1 flex min-h-screen flex-col">
      <header className="border-fg-3/40 bg-bg-0/95 flex items-center justify-between gap-6 border-b-2 px-6 py-4 backdrop-blur">
        <div className="flex items-center gap-6">
          <h1 className="font-display text-fg-0 text-lg font-semibold">
            radio.gofestivals <span className="text-magenta">admin</span>
          </h1>
          <nav className="flex gap-1">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'rounded-md px-3 py-1.5 font-mono text-[11px] uppercase tracking-widest transition-colors',
                  isActive(pathname, item.href)
                    ? 'bg-bg-2 text-fg-0'
                    : 'text-fg-2 hover:bg-bg-2 hover:text-fg-0',
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-fg-2 font-mono text-xs uppercase tracking-widest">
            {me.name ?? me.email}
          </span>
          <button
            type="button"
            onClick={() => logout()}
            className="border-fg-3 text-fg-1 hover:border-magenta hover:text-fg-0 rounded-md border px-3 py-1.5 font-mono text-[11px] uppercase tracking-widest transition-colors"
          >
            Logout
          </button>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
        {children}
      </main>
    </div>
  );
}
