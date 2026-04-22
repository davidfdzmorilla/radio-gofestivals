import { expect, test } from '@playwright/test';

test('home ES renders with Spanish copy', async ({ page }) => {
  await page.goto('/es');
  await expect(page.locator('h1')).toContainText('radio.gofestivals');
  await expect(page.getByText('Música electrónica, curada.')).toBeVisible();
});

test('home EN renders with English copy', async ({ page }) => {
  await page.goto('/en');
  await expect(page.locator('h1')).toContainText('radio.gofestivals');
  await expect(page.getByText('Electronic music, curated.')).toBeVisible();
});

test('hreflang tags are present', async ({ page }) => {
  await page.goto('/es');
  const enTag = await page.locator('link[rel="alternate"][hreflang="en"]').count();
  const esTag = await page.locator('link[rel="alternate"][hreflang="es"]').count();
  expect(enTag).toBeGreaterThan(0);
  expect(esTag).toBeGreaterThan(0);
});
