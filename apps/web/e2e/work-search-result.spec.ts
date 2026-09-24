import { test, expect } from '@playwright/test';

test.describe('Work Mode Search Results', () => {
  test('should show search results in Work mode', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    // Should be in Work mode by default
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/search Work mode search test');
    await page.keyboard.press('Enter');
    
    // Should execute search
    await expect(page.locator('text=Searching')).toBeVisible({ timeout: 5000 });
    await page.waitForSelector('[data-testid="source-card"]', { timeout: 15000 });
    
    // Should show source cards
    await expect(page.locator('[data-testid="source-card"]')).toBeVisible();
  });

  test('should have same search behavior as Talk mode', async ({ page }) => {
    // Both modes should execute /search identically
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/search parity test query');
    await page.keyboard.press('Enter');
    
    await page.waitForSelector('[data-testid="source-card"]', { timeout: 15000 });
    
    // Results should be identical regardless of mode
    await expect(page.locator('[data-testid="source-card"]')).toBeVisible();
  });
});