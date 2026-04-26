import { expect, test } from '@playwright/test';

const STORAGE_KEY = 'radio.gofestivals.preferredQuality';

// We need a station with 2+ streams. The seed/sync writes one in staging
// but in dev the dataset varies. The test discovers a candidate from the
// API and skips if none exists.
test('quality pills appear, switch updates audio.src and persists preference', async ({
  page,
  baseURL,
  request,
}) => {
  const apiBase = baseURL ?? 'http://127.0.0.1:3000';
  const probe = await request.get(`${apiBase}/api/v1/stations?curated=true&size=50`);
  if (!probe.ok()) test.skip(true, 'api not reachable in this env');
  const list = (await probe.json()) as { items: { slug: string }[] };

  let multiSlug: string | null = null;
  for (const item of list.items) {
    const detail = await request.get(`${apiBase}/api/v1/stations/${item.slug}`);
    if (!detail.ok()) continue;
    const body = (await detail.json()) as { streams: unknown[] };
    if (body.streams.length >= 2) {
      multiSlug = item.slug;
      break;
    }
  }

  if (!multiSlug) test.skip(true, 'no multi-stream station available');

  await page.goto(`/es/stations/${multiSlug}`);

  const pills = page.locator('button[aria-pressed]');
  await expect(pills).toHaveCount(await pills.count());
  const total = await pills.count();
  expect(total).toBeGreaterThanOrEqual(2);

  const activeBefore = await page.locator('button[aria-pressed="true"]').textContent();

  const playBtn = page.locator('button[aria-label="Reproducir"]').first();
  await expect(playBtn).toBeVisible();
  await playBtn.click();

  const audioSrcBefore = await page.evaluate(
    () => document.querySelector('audio')?.src ?? '',
  );

  const inactive = page.locator('button[aria-pressed="false"]').first();
  await inactive.click();

  await expect
    .poll(async () =>
      page.evaluate(() => document.querySelector('audio')?.src ?? ''),
    )
    .not.toBe(audioSrcBefore);

  const activeAfter = await page.locator('button[aria-pressed="true"]').textContent();
  expect(activeAfter).not.toBe(activeBefore);

  const stored = await page.evaluate(
    (key) => window.localStorage.getItem(key),
    STORAGE_KEY,
  );
  expect(['high', 'medium', 'low']).toContain(stored);
});
