import { expect, test } from '@playwright/test';

test('switching from ES to EN preserves path', async ({ page }) => {
  await page.goto('/es/genres/techno');
  await expect(page).toHaveURL(/\/es\/genres\/techno/);

  await page.selectOption('select[aria-label]', 'en');
  await page.waitForURL(/\/en\/genres\/techno/, { timeout: 10_000 });
  await expect(page).toHaveURL(/\/en\/genres\/techno/);
});

test('switching from EN to ES preserves path', async ({ page }) => {
  await page.goto('/en/genres/techno');
  await page.selectOption('select[aria-label]', 'es');
  await page.waitForURL(/\/es\/genres\/techno/, { timeout: 10_000 });
  await expect(page).toHaveURL(/\/es\/genres\/techno/);
});
