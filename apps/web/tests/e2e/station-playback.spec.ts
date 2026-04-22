import { expect, test } from '@playwright/test';

test('home → station card → detail → play shows GlobalPlayer', async ({ page }) => {
  await page.goto('/es');
  const firstStation = page.locator('a[href*="/es/stations/"]').first();
  if ((await firstStation.count()) === 0) {
    test.skip(true, 'no curated stations available');
  }
  const href = await firstStation.getAttribute('href');
  expect(href).toBeTruthy();
  await page.goto(href as string);

  const playBtn = page.locator('button[aria-label="Reproducir"]').first();
  await expect(playBtn).toBeVisible();
  await playBtn.click();

  const player = page.locator('.fixed.inset-x-0.bottom-0');
  await expect(player).toBeVisible();
});
