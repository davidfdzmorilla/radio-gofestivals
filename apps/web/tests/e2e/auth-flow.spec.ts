import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

const API = process.env.E2E_API_URL ?? 'http://127.0.0.1:8000';
const PASSWORD = 'e2e-password-1';

function uniqueEmail(): string {
  return `e2e-auth-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
}

async function deleteAccount(
  request: APIRequestContext,
  email: string,
): Promise<void> {
  // Limpieza vía API: la suite debe poder correr N veces contra el mismo
  // stack sin acumular cuentas.
  const login = await request.post(`${API}/api/v1/auth/login`, {
    data: { email, password: PASSWORD },
  });
  if (!login.ok()) return;
  const { access_token: token } = (await login.json()) as {
    access_token: string;
  };
  await request.delete(`${API}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { password: PASSWORD },
  });
}

async function registerViaUi(page: Page, email: string): Promise<void> {
  await page.goto('/es');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await page.getByRole('button', { name: 'Crear cuenta' }).first().click();
  const form = page.locator('form').filter({ has: page.locator('#auth-email') });
  await form.locator('#auth-email').fill(email);
  await form.locator('#auth-password').fill(PASSWORD);
  await form.locator('#auth-confirm').fill(PASSWORD);
  await form.locator('button[type="submit"]').click();
  // Sesión iniciada: el avatar del menú de usuario lleva el email
  await expect(page.locator(`button[aria-label="${email}"]`)).toBeVisible({
    timeout: 10_000,
  });
}

test('registro, perfil sin verificar, logout y login de nuevo', async ({
  page,
  request,
}) => {
  const email = uniqueEmail();
  try {
    await registerViaUi(page, email);

    // Perfil: email visible y aviso de verificación pendiente (B4)
    await page.goto('/es/profile');
    await expect(page.getByText(email)).toBeVisible();
    await expect(page.getByText('Email sin verificar')).toBeVisible();

    // Logout desde el menú de usuario
    await page.locator(`button[aria-label="${email}"]`).click();
    await page.getByRole('button', { name: 'Salir' }).click();
    await expect(page.getByRole('button', { name: 'Entrar' })).toBeVisible();

    // Login de nuevo (la cookie de refresh fue revocada en logout).
    // Volver a la home: el logout en /profile redirige a la página /login,
    // que tiene su propio formulario y ambigua los selectores del modal.
    await page.goto('/es');
    await page.getByRole('button', { name: 'Entrar' }).click();
    const loginForm = page
      .locator('form')
      .filter({ has: page.locator('#auth-email') });
    await loginForm.locator('#auth-email').fill(email);
    await loginForm.locator('#auth-password').fill(PASSWORD);
    await loginForm.locator('button[type="submit"]').click();
    await expect(page.locator(`button[aria-label="${email}"]`)).toBeVisible({
      timeout: 10_000,
    });
  } finally {
    await deleteAccount(request, email);
  }
});

test('la sesión sobrevive a una recarga (cookie de refresh)', async ({
  page,
  request,
}) => {
  const email = uniqueEmail();
  try {
    await registerViaUi(page, email);

    await page.reload();
    // El bootstrap restaura sesión vía /auth/refresh sin re-login
    await expect(page.locator(`button[aria-label="${email}"]`)).toBeVisible({
      timeout: 10_000,
    });
  } finally {
    await deleteAccount(request, email);
  }
});
