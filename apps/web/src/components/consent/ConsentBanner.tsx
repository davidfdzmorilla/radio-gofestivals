import { cookies } from 'next/headers';
import { getTranslations } from 'next-intl/server';
import { CONSENT_COOKIE, parseConsent } from '@/lib/consent';
import { ConsentChoiceClient } from './ConsentChoiceClient';

/**
 * Renders the consent banner only when the user has not chosen yet. The
 * decision is read SSR from the cookie so reloads don't flash the banner
 * for users who already accepted/rejected. Once mounted client-side, the
 * inner component re-checks the cookie to catch a choice made on another
 * tab.
 */
export async function ConsentBanner({ locale }: { locale: 'es' | 'en' }) {
  const cookieStore = await cookies();
  const initial = parseConsent(cookieStore.get(CONSENT_COOKIE)?.value);
  if (initial !== 'unknown') return null;

  const t = await getTranslations({ locale, namespace: 'consent' });
  return (
    <ConsentChoiceClient
      labels={{
        title: t('title'),
        body: t('body'),
        accept: t('accept'),
        reject: t('reject'),
        moreInfo: t('moreInfo'),
        privacyHref: `/${locale}/legal/privacy`,
      }}
    />
  );
}
