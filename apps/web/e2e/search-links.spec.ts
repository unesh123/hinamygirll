import { test, expect } from '@playwright/test';

test.describe('Search Result Links', () => {
  test('source cards should have clickable links', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/search Python 3.12 new features');
    await page.keyboard.press('Enter');
    
    await page.waitForSelector('[data-testid="source-card"]', { timeout: 15000 });
    
    const openButtons = page.locator('[data-testid="source-card"] button:has-text("Open")');
    const count = await openButtons.count();
    
    expect(count).toBeGreaterThan(0);
    
    for (let i = 0; i < count; i++) {
      const btn = openButtons.nth(i);
      const onclick = await btn.getAttribute('onclick');
      expect(onclick).toContain('window.open');
      expect(onclick).toMatch(/https?:\/\//);
    }
  });

  test('source cards should show domain', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/search GitHub Copilot features');
    await page.keyboard.press('Enter');
    
    await page.waitForSelector('[data-testid="source-card"]', { timeout: 15000 });
    
    const domain = page.locator('.source-domain').first();
    await expect(domain).toBeVisible();
    expect(await domain.textContent()).toMatch(/\w+\.\w+/);
  });

  test('source cards should show evidence status', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/search current AI news');
    await page.keyboard.press('Enter');
    
    await page.waitForSelector('[data-testid="source-card"]', { timeout: 15000 });
    
    // Should show evidence status (verified/partial/unverified)
    const status = page.locator('[data-testid="source-card"] [data-evidence-status]').first();
    await expect(status).toBeVisible();
  });
});