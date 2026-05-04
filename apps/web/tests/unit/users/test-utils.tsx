import { NextIntlClientProvider } from 'next-intl';
import type { ReactNode } from 'react';
import enMessages from '@/../messages/en.json';
import { ToastProvider } from '@/components/auth/ToastContext';
import { AuthProvider } from '@/lib/users/AuthContext';

interface ProvidersProps {
  children: ReactNode;
}

export function TestProviders({ children }: ProvidersProps) {
  return (
    <NextIntlClientProvider locale="en" messages={enMessages as Record<string, unknown>}>
      <AuthProvider>
        <ToastProvider>{children}</ToastProvider>
      </AuthProvider>
    </NextIntlClientProvider>
  );
}
