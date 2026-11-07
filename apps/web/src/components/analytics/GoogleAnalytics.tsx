'use client';

import Script from 'next/script';
import { useEffect, useState } from 'react';
import { CONSENT_COOKIE, parseConsent } from '@/lib/consent';
import { CONSENT_CHANGED_EVENT, validGaId } from '@/lib/analytics';

function readConsent(): ReturnType<typeof parseConsent> {
  const match = document.cookie
    .split(';')
    .map((p) => p.trim())
    .find((p) => p.startsWith(`${CONSENT_COOKIE}=`));
  return parseConsent(match?.slice(CONSENT_COOKIE.length + 1));
}

/**
 * Carga Google Analytics 4 solo si el usuario ha aceptado en el banner (RGPD/LSSI): hasta
 * entonces no se pide ni un byte a Google. Se renderiza vacío en servidor y en el primer render
 * del cliente, así no hay diferencias de hidratación. Sin señales de publicidad.
 */
export function GoogleAnalytics({ gaId }: { gaId: string | null | undefined }) {
  const id = validGaId(gaId);
  const [accepted, setAccepted] = useState(false);

  useEffect(() => {
    const sync = () => setAccepted(readConsent() === 'accepted');
    sync();
    window.addEventListener(CONSENT_CHANGED_EVENT, sync);
    return () => window.removeEventListener(CONSENT_CHANGED_EVENT, sync);
  }, []);

  if (!id || !accepted) return null;
  return (
    <>
      <Script src={`https://www.googletagmanager.com/gtag/js?id=${id}`} strategy="afterInteractive" />
      <Script id="ga-init" strategy="afterInteractive">
        {`window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', '${id}', { allow_google_signals: false, allow_ad_personalization_signals: false });`}
      </Script>
    </>
  );
}
