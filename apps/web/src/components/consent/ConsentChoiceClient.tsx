'use client';

import { useCallback, useEffect, useState } from 'react';
import { CONSENT_COOKIE, CONSENT_TTL_DAYS, parseConsent } from '@/lib/consent';

type Labels = {
  title: string;
  body: string;
  accept: string;
  reject: string;
  moreInfo: string;
  privacyHref: string;
};

const SECONDS_PER_DAY = 86_400;

function writeConsent(value: 'accepted' | 'rejected'): void {
  const maxAge = CONSENT_TTL_DAYS * SECONDS_PER_DAY;
  // The cookie is set by JS so HttpOnly is impossible — it's intentional,
  // the banner has to read its own state to disappear after a click.
  // Secure flag is dropped automatically on http://localhost during dev.
  const secure = window.location.protocol === 'https:' ? '; Secure' : '';
  document.cookie =
    `${CONSENT_COOKIE}=${value}; Max-Age=${maxAge}; Path=/; SameSite=Lax${secure}`;
}

function readConsentFromDocument(): ReturnType<typeof parseConsent> {
  if (typeof document === 'undefined') return 'unknown';
  const pairs = document.cookie.split(';').map((p) => p.trim());
  const match = pairs.find((p) => p.startsWith(`${CONSENT_COOKIE}=`));
  if (!match) return 'unknown';
  return parseConsent(match.slice(CONSENT_COOKIE.length + 1));
}

export function ConsentChoiceClient({ labels }: { labels: Labels }) {
  // Server-side this component is always rendered (parent already gated by
  // SSR cookie read). Once mounted, re-check from document.cookie in case
  // the user just chose on a different tab.
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    if (readConsentFromDocument() !== 'unknown') {
      setVisible(false);
    }
  }, []);

  const handle = useCallback((value: 'accepted' | 'rejected') => {
    writeConsent(value);
    setVisible(false);
  }, []);

  if (!visible) return null;

  return (
    <div
      role="dialog"
      aria-modal="false"
      aria-labelledby="rgf-consent-title"
      className="fixed inset-x-0 bottom-0 z-50 border-t border-fg-3 bg-bg-1 px-4 py-4 shadow-[0_-4px_20px_rgba(0,0,0,0.25)] sm:px-6"
    >
      <div className="mx-auto flex max-w-6xl flex-col gap-4 sm:flex-row sm:items-start sm:gap-6">
        <div className="flex-1 space-y-1.5">
          <p
            id="rgf-consent-title"
            className="font-display text-base font-semibold text-fg-0"
          >
            {labels.title}
          </p>
          <p className="text-sm leading-relaxed text-fg-1">
            {labels.body}{' '}
            <a
              href={labels.privacyHref}
              className="underline decoration-magenta/40 underline-offset-4 hover:decoration-magenta hover:text-fg-0"
            >
              {labels.moreInfo}
            </a>
            .
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2 sm:flex-col sm:items-stretch sm:gap-2">
          {/* Equal visual weight on both buttons — CNIL/ICO require it. */}
          <button
            type="button"
            onClick={() => handle('rejected')}
            className="inline-flex min-w-[120px] items-center justify-center rounded-full border border-fg-3 bg-bg-2 px-4 py-2 text-sm font-medium text-fg-0 transition-colors hover:bg-bg-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-magenta"
          >
            {labels.reject}
          </button>
          <button
            type="button"
            onClick={() => handle('accepted')}
            className="inline-flex min-w-[120px] items-center justify-center rounded-full border border-fg-3 bg-bg-2 px-4 py-2 text-sm font-medium text-fg-0 transition-colors hover:bg-bg-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-magenta"
          >
            {labels.accept}
          </button>
        </div>
      </div>
    </div>
  );
}
