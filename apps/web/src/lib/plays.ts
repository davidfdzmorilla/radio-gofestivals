import { ApiError } from '@/lib/api';
import { CONSENT_COOKIE, parseConsent } from '@/lib/consent';
import { getStoredToken, userFetch } from '@/lib/users/api';

const CLIENT_ID_KEY = 'rgf_client_id';
const SESSION_PLAYED_KEY = 'rgf_session_played';

function isBrowser(): boolean {
  return typeof window !== 'undefined';
}

export function hasConsent(): boolean {
  if (!isBrowser()) return false;
  const pairs = document.cookie.split(';').map((p) => p.trim());
  const match = pairs.find((p) => p.startsWith(`${CONSENT_COOKIE}=`));
  if (!match) return false;
  return parseConsent(match.slice(CONSENT_COOKIE.length + 1)) === 'accepted';
}

/**
 * Read the opaque client_id from localStorage, minting one if it does not
 * exist yet. Returns null if there is no browser context, or if the user
 * has not given consent — minting an id pre-consent would itself be
 * tracking under strict GDPR.
 */
export function getOrMintClientId(): string | null {
  if (!isBrowser() || !hasConsent()) return null;
  const existing = window.localStorage.getItem(CLIENT_ID_KEY);
  if (existing) return existing;
  const fresh = crypto.randomUUID();
  window.localStorage.setItem(CLIENT_ID_KEY, fresh);
  return fresh;
}

export function readClientId(): string | null {
  if (!isBrowser()) return null;
  return window.localStorage.getItem(CLIENT_ID_KEY);
}

export function clearClientId(): void {
  if (!isBrowser()) return;
  window.localStorage.removeItem(CLIENT_ID_KEY);
}

function readSessionPlayed(): Set<string> {
  if (!isBrowser()) return new Set();
  const raw = window.sessionStorage.getItem(SESSION_PLAYED_KEY);
  if (!raw) return new Set();
  try {
    const arr = JSON.parse(raw) as string[];
    return new Set(arr);
  } catch {
    return new Set();
  }
}

function writeSessionPlayed(set: Set<string>): void {
  if (!isBrowser()) return;
  window.sessionStorage.setItem(
    SESSION_PLAYED_KEY,
    JSON.stringify(Array.from(set)),
  );
}

export function alreadyPlayedThisSession(slug: string): boolean {
  return readSessionPlayed().has(slug);
}

function markPlayedThisSession(slug: string): void {
  const set = readSessionPlayed();
  set.add(slug);
  writeSessionPlayed(set);
}

interface PlayResponse {
  accepted: boolean;
  deduplicated: boolean;
}

/**
 * Fire a play event for the given slug. Returns null when no event was
 * sent — either consent missing, no identity available, or the same slug
 * already counted this session. The DB enforces the 24h dedup; this
 * client-side check just avoids superfluous requests.
 */
export async function recordPlay(slug: string): Promise<PlayResponse | null> {
  if (!isBrowser() || !hasConsent()) return null;
  if (alreadyPlayedThisSession(slug)) return null;

  // Identity resolution mirrors the backend: the JWT wins. Only mint a
  // client_id for anonymous listeners — logged-in users don't need one.
  const isLoggedIn = getStoredToken() !== null;
  let body: string;
  if (isLoggedIn) {
    body = '{}';
  } else {
    const clientId = getOrMintClientId();
    if (!clientId) return null; // consent was revoked between the gate and here
    body = JSON.stringify({ client_id: clientId });
  }

  const path = `/api/v1/stations/${slug}/play`;
  const response = await userFetch(path, { method: 'POST', body });
  if (!response.ok) {
    // 400 means the server saw no identity (race: consent flipped). 4xx
    // and 5xx errors here are non-fatal — losing a play event must not
    // break listening.
    if (response.status === 400) return null;
    throw new ApiError(response.status, path);
  }
  markPlayedThisSession(slug);
  return (await response.json()) as PlayResponse;
}

interface MergeResponse {
  merged: number;
  dropped_conflicts: number;
}

/**
 * Reassign the anonymous play history to the freshly logged-in user.
 * Called from AuthContext.login. Quietly skipped when there is no
 * client_id stored — nothing anonymous to migrate.
 */
export async function mergeAnonymousPlays(): Promise<MergeResponse | null> {
  if (!isBrowser()) return null;
  const clientId = readClientId();
  if (!clientId) return null;

  const path = '/api/v1/me/plays/merge';
  const response = await userFetch(path, {
    method: 'POST',
    body: JSON.stringify({ client_id: clientId }),
  });
  if (!response.ok) {
    throw new ApiError(response.status, path);
  }
  return (await response.json()) as MergeResponse;
}

export const __test__ = {
  CLIENT_ID_KEY,
  SESSION_PLAYED_KEY,
};
