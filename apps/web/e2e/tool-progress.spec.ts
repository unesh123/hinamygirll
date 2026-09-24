import { test, expect } from '@playwright/test';

test.describe('Tool Progress Display', () => {
  test('should show tool.started when search begins', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/search test progress');
    await page.keyboard.press('Enter');
    
    // Should show tool running state
    await expect(page.locator('text=Searching')).toBeVisible({ timeout: 5000 });
  });

  test('should show current stage during search', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/search long query for progress test');
    await page.keyboard.press('Enter');
    
    // Should show activity stages
    await expect(page.locator('[data-testid="activity-panel"]')).toBeVisible({ timeout: 5000 });
    
    const stages = ['Understand', 'Prepare', 'Wait', 'Prepare'];
    for (const stage of stages) {
      await expect(page.locator(`text=${stage}`)).toBeVisible({ timeout: 10000 });
    }
  });

  test('should show cancel action', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/search cancellable test');
    await page.keyboard.press('Enter');
    
    // Should show cancel button
    await expect(page.locator('button:has-text("Cancel")')).toBeVisible({ timeout: 5000 });
  });
});