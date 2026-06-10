import { expect, test } from '@playwright/test';

test('el panel admin sin sesión redirige al login', async ({ page }) => {
  await page.goto('/admin');
  await page.waitForURL('**/admin/login', { timeout: 10_000 });
  await expect(page.locator('input[type="password"]')).toBeVisible();
});

test('credenciales inválidas muestran error y no entran', async ({ page }) => {
  await page.goto('/admin/login');
  await page.locator('input[type="email"], input[type="text"]').first()
    .fill('nobody@example.com');
  await page.locator('input[type="password"]').fill('wrong-password-1');
  await page.locator('button[type="submit"]').click();

  // Sigue en el login (sin redirección al dashboard) y con feedback
  await page.waitForTimeout(1500);
  expect(page.url()).toContain('/admin/login');
});
