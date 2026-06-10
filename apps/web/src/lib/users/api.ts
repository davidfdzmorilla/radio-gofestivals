import { ApiError } from '@/lib/api';

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

// B3: el access token vive SOLO en memoria (ventana XSS mínima); la sesión
// larga es un refresh token rotatorio en cookie httpOnly que el JS no puede
// leer. Los nombres get/set/clearStoredToken se mantienen por compat.
let accessToken: string | null = null;

const LEGACY_TOKEN_KEY = 'user_token';

export function getStoredToken(): string | null {
  return accessToken;
}

export function setStoredToken(token: string): void {
  accessToken = token;
}

export function clearStoredToken(): void {
  accessToken = null;
}

/** Borra el JWT de 30 días que versiones anteriores guardaban en localStorage. */
export function clearLegacyStoredToken(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(LEGACY_TOKEN_KEY);
}

interface RefreshedSession {
  accessToken: string;
  user: unknown;
}

let refreshInFlight: Promise<RefreshedSession | null> | null = null;

/** Solo para tests: resetea el estado de sesión en memoria del módulo. */
export function __resetSessionStateForTests(): void {
  accessToken = null;
  refreshInFlight = null;
}

/**
 * Intenta restaurar/renovar la sesión con la cookie de refresh.
 * Single-flight: llamadas concurrentes comparten la misma petición.
 * Devuelve null si no hay sesión (sin cookie, caducada o revocada).
 */
export function tryRefreshSession(): Promise<RefreshedSession | null> {
  refreshInFlight ??= (async () => {
    try {
      const response = await fetch(`${BASE}/api/v1/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) {
        clearStoredToken();
        return null;
      }
      const data = (await response.json()) as {
        access_token: string;
        user: unknown;
      };
      setStoredToken(data.access_token);
      return { accessToken: data.access_token, user: data.user };
    } catch {
      return null;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

export interface UserFetchOptions extends RequestInit {
  /** Skip Authorization header even if a token is stored. */
  skipAuth?: boolean;
}

export async function userFetch(
  path: string,
  options: UserFetchOptions = {},
): Promise<Response> {
  const { skipAuth = false, headers = {}, ...rest } = options;

  const doFetch = (): Promise<Response> => {
    const finalHeaders: Record<string, string> = {
      Accept: 'application/json',
      ...(headers as Record<string, string>),
    };
    if (rest.body !== undefined && !finalHeaders['Content-Type']) {
      finalHeaders['Content-Type'] = 'application/json';
    }
    if (!skipAuth) {
      const token = getStoredToken();
      if (token) finalHeaders.Authorization = `Bearer ${token}`;
    }
    // credentials: la cookie de refresh está acotada a /api/v1/auth; en el
    // resto de rutas es un no-op, y en dev cross-origin (3000→8000) hace
    // falta para que login/refresh/logout transporten la cookie.
    return fetch(`${BASE}${path}`, {
      ...rest,
      credentials: 'include',
      headers: finalHeaders,
    });
  };

  const response = await doFetch();
  // Access token caducado (vive ~30 min): renovar con la cookie y
  // reintentar una vez. Los endpoints de auth quedan fuera del retry.
  if (
    response.status === 401 &&
    !skipAuth &&
    !path.startsWith('/api/v1/auth/')
  ) {
    const refreshed = await tryRefreshSession();
    if (refreshed) return doFetch();
  }
  return response;
}

export async function userFetchJson<T>(
  path: string,
  options: UserFetchOptions = {},
): Promise<T> {
  const response = await userFetch(path, options);
  if (!response.ok) {
    throw new ApiError(response.status, path);
  }
  return (await response.json()) as T;
}
