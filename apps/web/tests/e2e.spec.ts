import { test, expect } from '@playwright/test';

test.describe('E2E Suite', () => {
  test('App loads successfully and redirects to sign-in', async ({ page }) => {
    await page.goto('/');
    // Since we don't have Clerk testing tokens, we expect to be redirected to Clerk sign-in
    await expect(page).toHaveURL(/.*sign-in.*/);
  });
});
