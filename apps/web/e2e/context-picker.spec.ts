import { test, expect } from '@playwright/test';

test.describe('Context Picker (@ mentions)', () => {
  test('should open context picker when typing @', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('@');
    
    // Context picker should appear
    await expect(page.locator('[role="dialog"][aria-label="HINAA context picker"]')).toBeVisible();
  });

  test('should filter contexts when typing after @', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('@proj');
    
    await expect(page.locator('[role="dialog"][aria-label="HINAA context picker"]')).toBeVisible();
    // Should show project context
    await expect(page.locator('text=Current Project')).toBeVisible();
  });

  test('should select context with keyboard', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('@');
    await page.waitForSelector('[role="dialog"][aria-label="HINAA context picker"]');
    
    await page.keyboard.press('Enter');
    
    // Context chip should appear in composer
    await expect(page.locator('text=@project:current')).toBeVisible();
  });

  test('should persist context chips across mode changes', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('@');
    await page.waitForSelector('[role="dialog"][aria-label="HINAA context picker"]');
    await page.keyboard.press('Enter');
    
    // Switch to Talk mode
    await page.click('button:has-text("Talk")');
    
    // Context chip should still be there
    await expect(page.locator('text=@project:current')).toBeVisible();
  });

  test('should convert @search to /search command alias', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('@search');
    await page.waitForSelector('[role="dialog"][aria-label="HINAA context picker"]');
    
    // Should show search command in picker
    await expect(page.locator('text=Web Search')).toBeVisible();
    
    await page.keyboard.press('Enter');
    
    // Should convert to /search command chip
    await expect(page.locator('text=/search')).toBeVisible();
  });
});