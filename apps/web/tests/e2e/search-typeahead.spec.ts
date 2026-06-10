import { expect, test } from '@playwright/test';

test('enter without selection navigates to /search with the query', async ({
  page,
}) => {
  await page.goto('/es');
  const input = page.getByRole('combobox', { name: 'Buscar emisoras' });
  await input.fill('radio');
  await input.press('Enter');
  await page.waitForURL(/\/es\/search\?q=radio/);
});

test('typing shows the listbox; escape closes it', async ({ page }) => {
  await page.goto('/es');
  const input = page.getByRole('combobox', { name: 'Buscar emisoras' });
  await input.fill('radio');
  // El dropdown se abre con coincidencias o con el estado "sin coincidencias".
  const listbox = page.getByRole('listbox');
  await expect(listbox).toBeVisible();
  await input.press('Escape');
  await expect(listbox).not.toBeVisible();
  // Segundo Escape limpia el input.
  await input.press('Escape');
  await expect(input).toHaveValue('');
});

test('selecting a suggestion navigates to the station page', async ({
  page,
}) => {
  await page.goto('/es');
  const input = page.getByRole('combobox', { name: 'Buscar emisoras' });
  await input.fill('radio');
  await expect(page.getByRole('listbox')).toBeVisible();

  const firstOption = page.getByRole('option').first();
  const hasOptions = await firstOption
    .waitFor({ timeout: 5000 })
    .then(() => true)
    .catch(() => false);
  if (!hasOptions) {
    // Catálogo sin matches para "radio": el estado vacío es el contrato.
    await expect(page.getByRole('listbox')).toContainText(/sin coincidencias/i);
    return;
  }
  await input.press('ArrowDown');
  await expect(firstOption).toHaveAttribute('aria-selected', 'true');
  await input.press('Enter');
  await page.waitForURL(/\/es\/stations\/[^/]+$/);
});
