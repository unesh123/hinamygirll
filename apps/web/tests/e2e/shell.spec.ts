import { expect, test } from "@playwright/test";

/**
 * Shell v2 smoke: both modes load by URL, the mode switch and command palette
 * work, and the Integrations hub renders. Desktop-only: the mobile projects
 * collapse the page nav and are covered by mobile.spec.ts.
 */
test.beforeEach(async ({ isMobile }) => {
  test.skip(isMobile, "Shell v2 chrome is verified on desktop; mobile layout is covered elsewhere.");
});

test("workspace mode loads with chat composer and the mode switch", async ({ page }) => {
  await page.goto("/workspace");
  await expect(page.getByRole("radio", { name: /Workspace/ })).toBeChecked();
  await expect(page.getByPlaceholder("Ask HINA anything — chat mode...")).toBeVisible();
});

test("companion mode loads with the core HUD and persists across reloads", async ({ page }) => {
  await page.goto("/companion");
  await expect(page.getByRole("radio", { name: /Companion/ })).toBeChecked();
  await expect(page.getByTestId("companion-stage")).toBeVisible();
  await expect(page.getByRole("textbox", { name: /^Message/ })).toBeVisible();
  await expect(page.locator(".dich-showroom-root")).toHaveCount(0);
  await page.goto("/");
  await expect(page).toHaveURL(/\/companion$/);
});

test("mode switch navigates between modes", async ({ page }) => {
  await page.goto("/workspace");
  await page.getByRole("radio", { name: /Companion/ }).click();
  await expect(page).toHaveURL(/\/companion$/);
  await expect(page.getByTestId("companion-stage")).toBeVisible();
  await page.getByRole("radio", { name: /Workspace/ }).click();
  await expect(page).toHaveURL(/\/workspace$/);
});

test("command palette opens with Ctrl+K and navigates to a page", async ({ page }) => {
  await page.goto("/workspace");
  await page.keyboard.press("Control+k");
  const palette = page.getByRole("dialog", { name: "Command palette" });
  await expect(palette).toBeVisible();
  await page.getByRole("combobox", { name: "Search commands" }).fill("integrations");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/integrations$/);
  await expect(page.getByRole("heading", { name: "Integrations", level: 1 })).toBeVisible();
  await expect(palette).toBeHidden();
});

test("integrations hub lists connectors and degrades gracefully", async ({ page }) => {
  await page.goto("/integrations");
  await expect(page.getByRole("heading", { name: "Integrations", level: 1 })).toBeVisible();
  await expect(page.getByRole("list", { name: "Connectors" })).toBeVisible();
  await expect(page.getByRole("searchbox", { name: "Search skills" })).toBeVisible();
});

test("theme toggle switches and persists the theme", async ({ page }) => {
  await page.goto("/workspace");
  await page.getByRole("button", { name: /Switch to (light|dark) theme/ }).click();
  const first = await page.evaluate(() => document.documentElement.getAttribute("data-theme"));
  await page.reload();
  expect(await page.evaluate(() => document.documentElement.getAttribute("data-theme"))).toBe(first);
});
