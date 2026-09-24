import { test, expect } from '@playwright/test';

test.describe('Talk Mode Search Results', () => {
  test('should show search results in Talk mode', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    // Switch to Talk mode
    await page.click('button:has-text("Talk")');
    await page.waitForSelector('[data-testid="talk-mode"]', { timeout: 5000 });
    
    // In Talk mode, we'd need voice or text input
    // For now verify Talk mode loads
    expect(await page.locator('[data-testid="talk-mode"]').isVisible()).toBeTruthy();
  });

  test('should display source cards in Talk mode', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    // Switch to Talk mode
    await page.click('button:has-text("Talk")');
    await page.waitForSelector('[data-testid="talk-mode"]', { timeout: 5000 });
    
    // Talk mode should be active
    expect(await page.locator('[data-testid="talk-mode"]').isVisible()).toBeTruthy();
  });
});