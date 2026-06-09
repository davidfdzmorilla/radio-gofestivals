export type ConsentState = 'accepted' | 'rejected' | 'unknown';

export const CONSENT_COOKIE = 'rgf_consent';
export const CONSENT_TTL_DAYS = 180;

/**
 * Pure parser shared between server and client. Anything other than the two
 * canonical strings is treated as `unknown` — we re-prompt the user. That
 * includes cookies set by a previous version with a different schema.
 */
export function parseConsent(raw: string | null | undefined): ConsentState {
  if (raw === 'accepted' || raw === 'rejected') return raw;
  return 'unknown';
}
