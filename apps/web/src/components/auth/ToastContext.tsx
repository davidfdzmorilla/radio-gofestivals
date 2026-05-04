'use client';

import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from 'react';
import { CheckCircle2, Info, TriangleAlert, X } from 'lucide-react';
import { cn } from '@/lib/utils';

export type ToastTone = 'info' | 'success' | 'error' | 'warning';

interface ToastAction {
  label: string;
  onClick: () => void;
}

export interface Toast {
  id: number;
  tone: ToastTone;
  message: string;
  action?: ToastAction;
}

interface ToastContextValue {
  show: (
    message: string,
    options?: { tone?: ToastTone; action?: ToastAction; duration?: number },
  ) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let nextId = 1;
const DEFAULT_DURATION = 4000;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const show = useCallback<ToastContextValue['show']>((message, options) => {
    const id = nextId++;
    const toast: Toast = {
      id,
      tone: options?.tone ?? 'info',
      message,
      action: options?.action,
    };
    setToasts((prev) => [...prev, toast]);
    const duration = options?.duration ?? DEFAULT_DURATION;
    if (duration > 0) {
      setTimeout(() => dismiss(id), duration);
    }
  }, [dismiss]);

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (ctx === null) {
    throw new Error('useToast must be used within <ToastProvider>');
  }
  return ctx;
}

const TONE_STYLES: Record<ToastTone, string> = {
  info: 'border-fg-3/40 bg-bg-2 text-fg-0',
  success: 'border-cyan/40 bg-cyan-soft/60 text-cyan',
  error: 'border-magenta/40 bg-magenta-soft/60 text-warm',
  warning: 'border-warm/40 bg-magenta-soft/40 text-warm',
};

function ToastIcon({ tone }: { tone: ToastTone }) {
  if (tone === 'success') return <CheckCircle2 size={16} />;
  if (tone === 'error' || tone === 'warning')
    return <TriangleAlert size={16} />;
  return <Info size={16} />;
}

function ToastViewport({
  toasts,
  onDismiss,
}: {
  toasts: Toast[];
  onDismiss: (id: number) => void;
}) {
  if (toasts.length === 0) return null;
  return (
    <div
      role="region"
      aria-label="Notifications"
      className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4 sm:bottom-6 sm:left-auto sm:right-6 sm:items-end"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          role="alert"
          className={cn(
            'pointer-events-auto flex w-full max-w-md items-start gap-3 rounded-md border px-3 py-2.5 shadow-sticker-lg backdrop-blur',
            TONE_STYLES[t.tone],
          )}
        >
          <span className="mt-0.5 shrink-0">
            <ToastIcon tone={t.tone} />
          </span>
          <div className="flex-1 text-sm">
            <p>{t.message}</p>
            {t.action ? (
              <button
                type="button"
                onClick={() => {
                  t.action!.onClick();
                  onDismiss(t.id);
                }}
                className="mt-1 font-mono text-[10px] uppercase tracking-widest underline underline-offset-2 hover:no-underline"
              >
                {t.action.label}
              </button>
            ) : null}
          </div>
          <button
            type="button"
            onClick={() => onDismiss(t.id)}
            aria-label="Dismiss"
            className="text-fg-2 hover:text-fg-0 transition-colors"
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
