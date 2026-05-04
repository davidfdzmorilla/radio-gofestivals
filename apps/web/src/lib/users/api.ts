import { ApiError } from '@/lib/api';

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

const TOKEN_KEY = 'user_token';

export function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(TOKEN_KEY);
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
  return fetch(`${BASE}${path}`, { ...rest, headers: finalHeaders });
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
