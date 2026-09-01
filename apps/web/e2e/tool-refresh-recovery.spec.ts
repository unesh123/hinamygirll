import { test, expect } from '@playwright/test';

test.describe('Tool Refresh Recovery', () => {
  test('should restore search results after page refresh', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/search refresh recovery test');
    await page.keyboard.press('Enter');
    
    // Wait for results
    await page.waitForSelector('[data-testid="source-card"]', { timeout: 15000 });
    
    // Refresh page
    await page.reload();
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    // Source cards should be restored
    await expect(page.locator('[data-testid="source-card"]')).toBeVisible({ timeout: 5000 });
  });

  test('should restore tool activity after page refresh', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/search test activity restore');
    await page.keyboard.press('Enter');
    
    await page.waitForSelector('[data-testid="source-card"]', { timeout: 15000 });
    
    // Refresh page
    await page.reload();
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    // Tool activity should be restored
    await expect(page.locator('[data-testid="activity-panel"]')).toBeVisible({ timeout: 5000 });
  });
});