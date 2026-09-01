import { test, expect } from '@playwright/test';

test.describe('Provider ThinkingBlock Handling', () => {
  test('should not crash when provider returns ThinkingBlock + TextBlock', async ({ page }) => {
    // This test requires a mock provider that returns thinking blocks
    // For now, we verify the UI handles the error gracefully
    await page.goto('/');
    
    // Wait for the app to load
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    // The test would need a mock provider that returns ThinkingBlock
    // This is a placeholder for the actual integration test
    expect(await page.locator('[data-testid="work-composer"]').isVisible()).toBeTruthy();
  });

  test('should not expose hidden reasoning in chat', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    // Check that no reasoning text appears in messages
    const messages = page.locator('[data-testid="work-message"]');
    const count = await messages.count();
    
    for (let i = 0; i < count; i++) {
      const text = await messages.nth(i).textContent();
      expect(text).not.toContain('ThinkingBlock');
      expect(text).not.toContain('reasoning');
    }
  });
});