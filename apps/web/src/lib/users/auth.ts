import {
  AuthResponseSchema,
  UserSchema,
  type AuthResponse,
  type User,
} from './types';
import { userFetch } from './api';

/**
 * Maps backend status codes to typed error codes the UI knows about.
 * Anything else falls through to `unknown_<status>`.
 */
function mapAuthError(
  status: number,
  detail: string | undefined,
): string {
  if (status === 400 && detail === 'email_already_registered') {
    return 'email_already_exists';
  }
  if (status === 401) return 'invalid_credentials';
  if (status === 422) return 'invalid_payload';
  if (status === 429) return 'rate_limit_exceeded';
  return `unknown_${status}`;
}

async function readDetail(response: Response): Promise<string | undefined> {
  try {
    const data = (await response.json()) as { detail?: unknown };
    return typeof data.detail === 'string' ? data.detail : undefined;
  } catch {
    return undefined;
  }
}

export async function registerUser(
  email: string,
  password: string,
): Promise<AuthResponse> {
  const response = await userFetch('/api/v1/auth/register', {
    method: 'POST',
    skipAuth: true,
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    throw new Error(mapAuthError(response.status, await readDetail(response)));
  }
  return AuthResponseSchema.parse(await response.json());
}

export async function loginUser(
  email: string,
  password: string,
): Promise<AuthResponse> {
  const response = await userFetch('/api/v1/auth/login', {
    method: 'POST',
    skipAuth: true,
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    throw new Error(mapAuthError(response.status, await readDetail(response)));
  }
  return AuthResponseSchema.parse(await response.json());
}

export async function getMe(): Promise<User> {
  const response = await userFetch('/api/v1/auth/me');
  if (!response.ok) {
    throw new Error(`me_failed_${response.status}`);
  }
  return UserSchema.parse(await response.json());
}

export async function deleteAccount(password: string): Promise<void> {
  const response = await userFetch('/api/v1/auth/me', {
    method: 'DELETE',
    body: JSON.stringify({ password }),
  });
  if (!response.ok) {
    throw new Error(mapAuthError(response.status, await readDetail(response)));
  }
}

export async function forgotPassword(email: string): Promise<void> {
  const response = await userFetch('/api/v1/auth/forgot-password', {
    method: 'POST',
    skipAuth: true,
    body: JSON.stringify({ email }),
  });
  if (!response.ok) {
    throw new Error(mapAuthError(response.status, await readDetail(response)));
  }
}

export async function resetPassword(
  token: string,
  newPassword: string,
): Promise<void> {
  const response = await userFetch('/api/v1/auth/reset-password', {
    method: 'POST',
    skipAuth: true,
    body: JSON.stringify({ token, new_password: newPassword }),
  });
  if (!response.ok) {
    if (response.status === 400) throw new Error('invalid_or_expired_token');
    throw new Error(mapAuthError(response.status, await readDetail(response)));
  }
}
