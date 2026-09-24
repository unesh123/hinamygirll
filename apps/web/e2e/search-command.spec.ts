import { test, expect } from '@playwright/test';

test.describe('Search Command (/search)', () => {
  test('should execute search and show tool.running state', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/search latest official Vite PWA documentation');
    await page.keyboard.press('Enter');
    
    // Should show tool running state
    await expect(page.locator('text=Searching')).toBeVisible({ timeout: 5000 });
    
    // Should show tool progress
    await expect(page.locator('[data-testid="tool-progress"]')).toBeVisible({ timeout: 10000 });
  });

  test('should show You.com results with source cards', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/search React 19 release date');
    await page.keyboard.press('Enter');
    
    // Wait for results
    await page.waitForSelector('[data-testid="source-card"]', { timeout: 15000 });
    
    // Should have at least one source card
    const sourceCards = page.locator('[data-testid="source-card"]');
    await expect(sourceCards.first()).toBeVisible();
    
    // Source card should have title, domain, snippet, and link
    const firstCard = sourceCards.first();
    await expect(firstCard.locator('.source-title')).toBeVisible();
    await expect(firstCard.locator('.source-domain')).toBeVisible();
    await expect(firstCard.locator('.source-snippet')).toBeVisible();
    await expect(firstCard.locator('button:has-text("Open")')).toBeVisible();
  });

  test('should have clickable links with valid http/https href', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/search TypeScript 5.3 release');
    await page.keyboard.press('Enter');
    
    await page.waitForSelector('[data-testid="source-card"]', { timeout: 15000 });
    
    const openButton = page.locator('[data-testid="source-card"] button:has-text("Open")').first();
    const href = await openButton.getAttribute('onclick');
    
    // Should have window.open with valid URL
    expect(href).toContain('window.open');
    expect(href).toMatch(/https?:\/\//);
  });

  test('should show tool.succeeded state', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/search simple test query');
    await page.keyboard.press('Enter');
    
    // Wait for completion
    await page.waitForSelector('text=Completed', { timeout: 15000 });
    
    // Should show assistant grounded response
    await expect(page.locator('[data-testid="work-message"]:has-text("search")')).toBeVisible({ timeout: 10000 });
  });

  test('should not show "I\'ll search" dead-end text', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/search test query');
    await page.keyboard.press('Enter');
    
    // Wait for response
    await page.waitForSelector('[data-testid="work-message"]', { timeout: 15000 });
    
    const messages = page.locator('[data-testid="work-message"]');
    const count = await messages.count();
    
    for (let i = 0; i < count; i++) {
      const text = await messages.nth(i).textContent();
      expect(text).not.toContain("I'll search");
      expect(text).not.toContain("Let me search");
      expect(text).not.toContain("I'm searching");
    }
  });
});