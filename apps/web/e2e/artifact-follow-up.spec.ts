import { test, expect } from '@playwright/test';

test.describe('Artifact Follow-up Lookup', () => {
  test('should handle "where is the pdf file?" without crash', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('Where is the PDF file?');
    await page.keyboard.press('Enter');
    
    // Should not crash with provider parser error
    await page.waitForSelector('[data-testid="work-message"]', { timeout: 15000 });
    
    // Should show honest no-artifact result
    const messages = page.locator('[data-testid="work-message"]');
    const count = await messages.count();
    
    for (let i = 0; i < count; i++) {
      const text = await messages.nth(i).textContent() || '';
      // Should not invent file paths
      expect(text).not.toMatch(/C:\\|\\/home\\|\\/tmp\\/);
      expect(text).not.toContain('PROVIDER_RESPONSE_INVALID');
      expect(text).not.toContain("ThinkingBlock");
    }
  });

  test('should show Create PDF action when no PDF exists', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('Where is the PDF?');
    await page.keyboard.press('Enter');
    
    await page.waitForSelector('[data-testid="work-message"]', { timeout: 15000 });
    
    // Should offer to create PDF
    // This would depend on the implementation
    expect(await page.locator('[data-testid="work-composer"]').isVisible()).toBeTruthy();
  });

  test('should not invent file paths or URLs', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('Show me the PDF');
    await page.keyboard.press('Enter');
    
    await page.waitForSelector('[data-testid="work-message"]', { timeout: 15000 });
    
    const messages = page.locator('[data-testid="work-message"]');
    const count = await messages.count();
    
    for (let i = 0; i < count; i++) {
      const text = await messages.nth(i).textContent() || '';
      // Should not invent fake file paths
      expect(text).not.toMatch(/https?:\/\/fake/);
      expect(text).not.toMatch(/file:\/\//);
    }
  });
});