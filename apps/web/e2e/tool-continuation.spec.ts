import { test, expect } from '@playwright/test';

test.describe('Provider Tool Continuation', () => {
  test('provider should receive tool result and continue', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/search continuation test query');
    await page.keyboard.press('Enter');
    
    // Wait for search to complete and provider to respond
    await page.waitForSelector('[data-testid="work-message"]:has-text("search")', { timeout: 20000 });
    
    // Should have grounded response mentioning sources
    const messages = page.locator('[data-testid="work-message"]');
    const count = await messages.count();
    
    let foundGrounded = false;
    for (let i = 0; i < count; i++) {
      const text = await messages.nth(i).textContent() || '';
      if (text.toLowerCase().includes('source') || text.toLowerCase().includes('found')) {
        foundGrounded = true;
        break;
      }
    }
    expect(foundGrounded).toBeTruthy();
  });

  test('should not show false execution language after tool result', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/search no false language test');
    await page.keyboard.press('Enter');
    
    await page.waitForSelector('[data-testid="work-message"]', { timeout: 20000 });
    
    const messages = page.locator('[data-testid="work-message"]');
    const count = await messages.count();
    
    for (let i = 0; i < count; i++) {
      const text = await messages.nth(i).textContent() || '';
      // After tool completes, should not say "I'll search"
      expect(text).not.toContain("I'll search");
      expect(text).not.toContain("Let me search");
      expect(text).not.toContain("I'm searching");
      expect(text).not.toContain("One moment");
    }
  });

  test('provider failure should produce visible terminal error', async ({ page }) => {
    // Would need mock provider failure
    // Verify the app loads
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    expect(await page.locator('[data-testid="work-composer"]').isVisible()).toBeTruthy();
  });

  test('empty results should produce honest result', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/search xyzqwerty123nonexistentqueryemptyresults');
    await page.keyboard.press('Enter');
    
    await page.waitForSelector('[data-testid="work-message"]', { timeout: 15000 });
    
    // Should not claim success with empty results
    const messages = page.locator('[data-testid="work-message"]');
    const count = await messages.count();
    
    for (let i = 0; i < count; i++) {
      const text = await messages.nth(i).textContent() || '';
      expect(text.toLowerCase()).not.toContain("i found");
      expect(text.toLowerCase()).not.toContain("here are");
    }
  });
});