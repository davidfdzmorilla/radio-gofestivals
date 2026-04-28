import { adminFetch, clearToken, getStoredToken, storeToken } from './api';

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_at: string;
}

export interface AdminMe {
  id: string;
  email: string;
  name: string | null;
  last_login_at: string | null;
}

export class LoginError extends Error {
  constructor(public readonly code: string) {
    super(code);
    this.name = 'LoginError';
  }
}

export async function login(
  email: string,
  password: string,
): Promise<LoginResponse> {
  const response = await adminFetch('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
    skipAuth: true,
  });

  if (!response.ok) {
    if (response.status === 401) throw new LoginError('invalid_credentials');
    if (response.status === 429) throw new LoginError('rate_limit_exceeded');
    throw new LoginError(`login_failed_${response.status}`);
  }

  const data = (await response.json()) as LoginResponse;
  storeToken(data.access_token);
  return data;
}

export async function getMe(): Promise<AdminMe> {
  const response = await adminFetch('/auth/me');
  if (!response.ok) throw new Error('unauthorized');
  return (await response.json()) as AdminMe;
}

export function logout(): void {
  clearToken();
  if (typeof window !== 'undefined') {
    window.location.href = '/admin/login';
  }
}

export function isAuthenticated(): boolean {
  return getStoredToken() !== null;
}
