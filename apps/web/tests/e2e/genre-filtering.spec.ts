import { expect, test } from '@playwright/test';

test('genre page shows stations or empty state', async ({ page }) => {
  await page.goto('/es/genres/techno');
  await expect(page.locator('h1')).toContainText('Techno');

  const stationCount = await page.locator('a[href*="/es/stations/"]').count();
  if (stationCount === 0) {
    // empty state (múltiples copies mencionan "estaciones" — .first() resuelve ambigüedad)
    await expect(
      page.getByText(/Todavía no hay estaciones|sin estaciones/i).first(),
    ).toBeVisible();
  } else {
    expect(stationCount).toBeGreaterThan(0);
  }
});
