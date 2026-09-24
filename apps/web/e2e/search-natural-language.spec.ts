import { test, expect } from '@playwright/test';

test.describe('Natural Language Search Intent', () => {
  test('should detect "latest" queries as search intent', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('What are the latest React 19 features?');
    await page.keyboard.press('Enter');
    
    // Should trigger web_search tool
    await expect(page.locator('text=Searching')).toBeVisible({ timeout: 5000 });
  });

  test('should detect "find me links" as search intent', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('Find me links to official TypeScript documentation');
    await page.keyboard.press('Enter');
    
    await expect(page.locator('text=Searching')).toBeVisible({ timeout: 5000 });
  });

  test('should detect "where can I watch" as search intent', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('Where can I watch the latest anime?');
    await page.keyboard.press('Enter');
    
    await expect(page.locator('text=Searching')).toBeVisible({ timeout: 5000 });
  });
});