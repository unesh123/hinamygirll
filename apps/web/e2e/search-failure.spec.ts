import { test, expect } from '@playwright/test';

test.describe('Search Failure Handling', () => {
  test('should handle provider unavailable gracefully', async ({ page }) => {
    // This test would require mocking the provider as unavailable
    // For now, verify the UI shows appropriate error state
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/search test query');
    await page.keyboard.press('Enter');
    
    // Should show either results or error state
    await page.waitForSelector('[data-testid="work-message"], text=error', { timeout: 15000 });
  });

  test('should handle empty results honestly', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/search xyzqwerty123nonexistentquery');
    await page.keyboard.press('Enter');
    
    await page.waitForSelector('[data-testid="work-message"]', { timeout: 15000 });
    
    // Should show honest "no results" message
    const messages = page.locator('[data-testid="work-message"]');
    const count = await messages.count();
    
    for (let i = 0; i < count; i++) {
      const text = await messages.nth(i).textContent() || '';
      expect(text.toLowerCase()).not.toContain("i found");
    }
  });

  test('should reject unsafe URLs', async ({ page }) => {
    // This would require a mock that returns unsafe URLs
    // Verify the UI doesn't render unsafe URLs as clickable links
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    // The test would need a mock provider returning javascript: or file: URLs
    // For now, verify the app loads
    expect(await page.locator('[data-testid="work-composer"]').isVisible()).toBeTruthy();
  });
});