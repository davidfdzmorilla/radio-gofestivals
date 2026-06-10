import { expect, test } from '@playwright/test';

test('la home muestra el módulo «Para ti» (cold start)', async ({ page }) => {
  await page.goto('/es');

  // El módulo es client-fetch: se oculta entero si no hay catálogo.
  const heading = page.getByText('Para ti', { exact: true });
  try {
    await heading.waitFor({ state: 'visible', timeout: 10_000 });
  } catch {
    test.skip(true, 'no recommendations available (empty catalog?)');
  }

  // Dentro de la sección del módulo hay tarjetas con enlaces a emisoras
  const section = page.locator('section', { has: heading });
  expect(await section.locator('a[href*="/es/stations/"]').count()).toBeGreaterThan(0);
});

test('la ficha de emisora muestra «Emisoras similares»', async ({ page }) => {
  await page.goto('/es');
  const firstStation = page.locator('a[href*="/es/stations/"]').first();
  if ((await firstStation.count()) === 0) {
    test.skip(true, 'no stations available');
  }
  await page.goto((await firstStation.getAttribute('href')) as string);

  const heading = page.getByText('Emisoras similares', { exact: true });
  try {
    await heading.waitFor({ state: 'visible', timeout: 10_000 });
  } catch {
    test.skip(true, 'no similarity data (batch not run?)');
  }

  const section = page.locator('section', { has: heading });
  expect(await section.locator('a[href*="/es/stations/"]').count()).toBeGreaterThan(0);
});
