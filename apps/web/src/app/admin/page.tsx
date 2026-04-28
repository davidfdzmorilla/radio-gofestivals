'use client';

import { useEffect, useState } from 'react';
import { type AdminMe, getMe } from '@/lib/admin/auth';

export default function AdminDashboard() {
  const [me, setMe] = useState<AdminMe | null>(null);

  useEffect(() => {
    let cancelled = false;
    getMe()
      .then((data) => {
        if (!cancelled) setMe(data);
      })
      .catch(() => {
        // Layout already handles redirect on auth failure.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!me) return null;

  const lastLogin = me.last_login_at
    ? new Date(me.last_login_at).toLocaleString()
    : 'First login';

  return (
    <div className="space-y-8">
      <div>
        <h2 className="font-display text-fg-0 text-3xl font-bold">
          Welcome, {me.name ?? me.email}
        </h2>
        <p className="text-fg-2 mt-1 font-mono text-xs uppercase tracking-widest">
          Last login · {lastLogin}
        </p>
      </div>

      <section className="border-fg-3/40 bg-bg-2/40 rounded-lg border p-6">
        <h3 className="font-display text-fg-0 text-lg font-semibold">
          Próximas funcionalidades
        </h3>
        <ul className="text-fg-2 mt-3 space-y-1 text-sm">
          <li>· Gestión de stations (Tier 1, próxima sesión)</li>
          <li>· Gestión de géneros (Tier 2)</li>
          <li>· Operaciones: force sync, auto-curate (Tier 3)</li>
          <li>· Dashboard con métricas + audit log viewer (Tier 4)</li>
        </ul>
      </section>
    </div>
  );
}
