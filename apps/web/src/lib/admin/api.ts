const ADMIN_TOKEN_KEY = 'admin_token';
const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const ADMIN_PREFIX = '/api/v1/admin';

export function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(ADMIN_TOKEN_KEY);
}

export function storeToken(token: string): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(ADMIN_TOKEN_KEY, token);
}

export function clearToken(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(ADMIN_TOKEN_KEY);
}

export interface AdminFetchOptions extends RequestInit {
  skipAuth?: boolean;
}

export async function adminFetch(
  path: string,
  options: AdminFetchOptions = {},
): Promise<Response> {
  const { skipAuth = false, headers = {}, ...rest } = options;

  const finalHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ...(headers as Record<string, string>),
  };

  if (!skipAuth) {
    const token = getStoredToken();
    if (token) {
      finalHeaders.Authorization = `Bearer ${token}`;
    }
  }

  const response = await fetch(`${API_BASE}${ADMIN_PREFIX}${path}`, {
    ...rest,
    headers: finalHeaders,
  });

  if (response.status === 401 && !skipAuth) {
    clearToken();
    if (typeof window !== 'undefined') {
      window.location.href = '/admin/login';
    }
  }

  return response;
}
