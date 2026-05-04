'use client';

import { useEffect, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/lib/utils';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** Allow ESC + backdrop click to close. Set false while submitting. */
  dismissable?: boolean;
  /** Additional class names for the inner panel (sizing, etc). */
  panelClassName?: string;
  children: ReactNode;
}

/**
 * Portal-rendered modal that always sits at z-50 over the document body.
 *
 * Putting modals into a portal sidesteps stacking contexts created by
 * parents with `transform`, `filter`, or `backdrop-filter` (e.g. the
 * GlobalPlayer or station cards), so the modal never gets clipped by
 * sibling layers.
 *
 * Layout: outer fixed scroll-y container (so tall modals are reachable
 * on short viewports) + flex centered child + inner panel.
 */
export function Modal({
  isOpen,
  onClose,
  dismissable = true,
  panelClassName,
  children,
}: ModalProps) {
  const [mounted, setMounted] = useState(false);

  // Lock body scroll while open and listen for ESC.
  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && dismissable) onClose();
    };
    window.addEventListener('keydown', handler);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', handler);
      document.body.style.overflow = prevOverflow;
    };
  }, [isOpen, dismissable, onClose]);

  if (!isOpen || !mounted) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[100] overflow-y-auto bg-bg-0/85 backdrop-blur"
      onClick={(e) => {
        if (dismissable && e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="flex min-h-full items-center justify-center p-4 sm:p-6"
        onClick={(e) => {
          if (dismissable && e.target === e.currentTarget) onClose();
        }}
      >
        <div
          className={cn(
            'border-fg-3/40 bg-bg-2 w-full max-w-md rounded-lg border shadow-sticker-lg',
            panelClassName,
          )}
        >
          {children}
        </div>
      </div>
    </div>,
    document.body,
  );
}
