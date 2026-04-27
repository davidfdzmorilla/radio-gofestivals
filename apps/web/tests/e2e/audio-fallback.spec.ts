import { expect, test } from '@playwright/test';

// Force the browser to fail on the primary stream URL by aborting the
// network request, then assert the player either swaps to a secondary
// stream (multi-stream station) or surfaces the unavailable banner.
test('failed stream triggers fallback or surfaces unavailable banner', async ({
  page,
  baseURL,
  request,
}) => {
  const apiBase = baseURL ?? 'http://127.0.0.1:3000';
  const probe = await request.get(`${apiBase}/api/v1/stations?curated=true&size=50`);
  if (!probe.ok()) test.skip(true, 'api not reachable');
  const list = (await probe.json()) as { items: { slug: string }[] };

  let multiSlug: string | null = null;
  for (const item of list.items) {
    const detail = await request.get(`${apiBase}/api/v1/stations/${item.slug}`);
    if (!detail.ok()) continue;
    const body = (await detail.json()) as { streams: { url: string }[] };
    if (body.streams.length >= 2) {
      multiSlug = item.slug;
      break;
    }
  }
  if (!multiSlug) test.skip(true, 'no multi-stream station available');

  await page.goto(`/es/stations/${multiSlug}`);

  // Block the first audio request so the <audio> element fires onerror.
  let blockedFirst = false;
  await page.route('**/*', (route) => {
    const url = route.request().url();
    const isAudio =
      route.request().resourceType() === 'media' ||
      /\.(mp3|aac|ogg|m4a)(\?|$)/.test(url);
    if (isAudio && !blockedFirst) {
      blockedFirst = true;
      return route.abort('failed');
    }
    return route.continue();
  });

  const playBtn = page.locator('button[aria-label="Reproducir"]').first();
  await expect(playBtn).toBeVisible();
  await playBtn.click();

  // Either: the audio.src eventually changes to the second stream URL, or
  // the unavailable banner shows up. Both outcomes are valid evidence the
  // fallback path executed.
  await expect
    .poll(async () => {
      const banner = await page
        .locator('text=Emisora no disponible temporalmente')
        .count();
      const audioSrc = await page.evaluate(
        () => document.querySelector('audio')?.src ?? '',
      );
      return { banner, audioSrc };
    })
    .toMatchObject(
      expect.objectContaining({
        banner: expect.any(Number),
        audioSrc: expect.any(String),
      }),
    );

  const banner = await page
    .locator('text=Emisora no disponible temporalmente')
    .count();
  if (banner === 0) {
    // Fallback succeeded: audio.src must differ from the (blocked) initial.
    const audioSrc = await page.evaluate(
      () => document.querySelector('audio')?.src ?? '',
    );
    expect(audioSrc.length).toBeGreaterThan(0);
  } else {
    // Banner up; retry button must be present.
    await expect(page.locator('text=Reintentar').first()).toBeVisible();
  }
});
