import { expect, test } from '@playwright/test';

test('favorito anónimo: corazón en la home y aparece en /favorites', async ({
  page,
}) => {
  await page.goto('/es');

  const heart = page
    .locator('button[aria-label="Añadir a favoritas"]')
    .first();
  if ((await heart.count()) === 0) {
    test.skip(true, 'no stations available');
  }

  await heart.click();
  await expect(
    page.locator('button[aria-label="Quitar de favoritas"]').first(),
  ).toBeVisible();

  await page.goto('/es/favorites');
  // Al menos una tarjeta con su corazón "quitar" (persistió en localStorage)
  await expect(
    page.locator('button[aria-label="Quitar de favoritas"]').first(),
  ).toBeVisible();

  // Quitarla deja la página en estado vacío
  await page
    .locator('button[aria-label="Quitar de favoritas"]')
    .first()
    .click();
  await expect(
    page.getByText('Aún no has guardado ninguna estación.'),
  ).toBeVisible();
});
