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

declare global {
  interface Window {
    /** Página y referrer de entrada, guardados en memoria hasta que se acepte el banner. */
    __rgfLanding?: { location: string; referrer: string };
  }
}

/**
 * Carga Google Analytics 4 solo si el usuario ha aceptado en el banner (RGPD/LSSI): hasta
 * entonces no se pide ni un byte a Google. Se renderiza vacío en servidor y en el primer render
 * del cliente, así no hay diferencias de hidratación. Sin señales de publicidad.
 */
export function GoogleAnalytics({ gaId }: { gaId: string | null | undefined }) {
  const id = validGaId(gaId);
  const [accepted, setAccepted] = useState(false);

  // Atribución: GA se carga DESPUÉS de aceptar el banner. Si el visitante llegó desde Google (o con
  // utm_*) y navegó antes de aceptar, en ese momento la URL ya no lleva utm y document.referrer
  // sigue siendo el de la entrada pero la sesión empezaría en la página actual: GA la clasifica
  // como directa o sin asignar. Se recuerdan SOLO en memoria (nada en storage ni red) la página
  // y el referrer de entrada, y el init los usa para abrir la sesión.
  useEffect(() => {
    window.__rgfLanding ??= { location: window.location.href, referrer: document.referrer };
  }, []);

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
var l = window.__rgfLanding;
var moved = !!l && l.location !== window.location.href;
var debug = /[?&]ga_debug=1(&|$)/.test((l && l.location) || window.location.href);
gtag('config', '${id}', { allow_google_signals: false, allow_ad_personalization_signals: false, send_page_view: !moved, debug_mode: debug });
if (moved) {
  gtag('event', 'page_view', { page_location: l.location, page_referrer: l.referrer });
  gtag('event', 'page_view', { page_location: window.location.href, page_referrer: l.location });
}`}
      </Script>
    </>
  );
}
