'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import {
  type AdminMe,
  getMe,
  isAuthenticated,
  logout,
} from '@/lib/admin/auth';
import '../globals.css';

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
      <header className="border-fg-3/40 bg-bg-0/95 flex items-center justify-between border-b-2 px-6 py-4 backdrop-blur">
        <h1 className="font-display text-fg-0 text-lg font-semibold">
          radio.gofestivals <span className="text-magenta">admin</span>
        </h1>
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
