import { expect, test } from '@playwright/test';

// Regression: switching from station A to station B without pausing first
// previously left the <audio> element frozen because the new src raced with
// the in-flight play() promise. The fix is in components/player/GlobalPlayer.tsx
// (consolidated effect that pauses, swaps src, loads, then plays again with
// AbortError handling).
test('switch station while previous is playing updates audio src to new station', async ({
  page,
}) => {
  await page.goto('/es');

  const stationLinks = page.locator('a[href*="/es/stations/"]');
  const count = await stationLinks.count();
  if (count < 2) {
    test.skip(true, 'need at least two curated stations to test switching');
  }

  const hrefA = await stationLinks.nth(0).getAttribute('href');
  const hrefB = await stationLinks.nth(1).getAttribute('href');
  expect(hrefA).toBeTruthy();
  expect(hrefB).toBeTruthy();
  expect(hrefA).not.toBe(hrefB);

  const slugA = (hrefA as string).split('/').pop() as string;
  const slugB = (hrefB as string).split('/').pop() as string;

  await page.goto(hrefA as string);
  const playA = page.locator('button[aria-label="Reproducir"]').first();
  await expect(playA).toBeVisible();
  await playA.click();

  const player = page.locator('.fixed.inset-x-0.bottom-0');
  await expect(player).toBeVisible();

  await expect
    .poll(async () => page.evaluate(() => document.querySelector('audio')?.src ?? ''))
    .toContain(slugA);

  // Switch without pausing: navigate to station B and click play.
  await page.goto(hrefB as string);
  const playB = page.locator('button[aria-label="Reproducir"]').first();
  await playB.click();

  await expect
    .poll(async () => page.evaluate(() => document.querySelector('audio')?.src ?? ''))
    .toContain(slugB);

  // Only a single <audio> element exists (no duplicates introduced by the swap).
  const audioCount = await page.evaluate(() => document.querySelectorAll('audio').length);
  expect(audioCount).toBe(1);
});
