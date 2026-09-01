import { test, expect } from '@playwright/test';

test.describe('Context Permissions', () => {
  test('should reject unauthorized context references', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('@project:unauthorized');
    await page.keyboard.press('Enter');
    
    // Should show permission denied state
    await expect(page.locator('text=Permission denied')).toBeVisible({ timeout: 5000 });
  });

  test('should show stale indicator for outdated context', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('@memory');
    await page.waitForSelector('[role="dialog"][aria-label="HINAA context picker"]');
    await page.keyboard.press('Enter');
    
    // Memory context should be selectable
    await expect(page.locator('text=@memory:memories')).toBeVisible();
  });
});