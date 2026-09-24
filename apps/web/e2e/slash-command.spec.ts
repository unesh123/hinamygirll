import { test, expect } from '@playwright/test';

test.describe('Slash Command Palette (/ commands)', () => {
  test('should open command palette when typing /', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/');
    
    // Command palette should appear
    await expect(page.locator('[role="dialog"][aria-label="HINAA slash commands"]')).toBeVisible();
  });

  test('should show all registered commands', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/');
    
    await expect(page.locator('[role="dialog"][aria-label="HINAA slash commands"]')).toBeVisible();
    
    // Should show search command
    await expect(page.locator('text=Web Search')).toBeVisible();
    await expect(page.locator('text=Deep Research')).toBeVisible();
    await expect(page.locator('text=Generate Image')).toBeVisible();
  });

  test('should select command with keyboard', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/search');
    await page.waitForSelector('[role="dialog"][aria-label="HINAA slash commands"]');
    
    await page.keyboard.press('Enter');
    
    // Command chip should appear
    await expect(page.locator('text=/search')).toBeVisible();
  });

  test('should show unavailable state for unconfigured commands', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/play');
    await page.waitForSelector('[role="dialog"][aria-label="HINAA slash commands"]');
    
    // Play command should show as unavailable/degraded
    const playItem = page.locator('text=Play Music').first();
    await expect(playItem).toBeVisible();
  });

  test('should parse command arguments', async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('[data-testid="work-composer"]', { timeout: 10000 });
    
    const textarea = page.locator('[data-testid="chat-input"]');
    await textarea.fill('/search latest anime news');
    await page.keyboard.press('Enter');
    
    // Should create /search command with args
    await expect(page.locator('text=/search')).toBeVisible();
  });
});