import { expect, test } from "@playwright/test";
import { isolateSettings } from "./helpers";

/**
 * Two complaints this guards. First, the saved-thread panel was unreachable:
 * the rail received `onToggleHistory` but never rendered a control for it, so
 * `historyOpen` could never become true. Second, the panel parsed
 * GET /v1/conversations as an envelope even though the endpoint answers with a
 * bare JSON array, so even when it did open the list was always empty.
 */
test.describe("Saved conversation history", () => {
  test("opens from the rail and lists the owner's real threads", async ({ page }) => {
    test.skip(
      test.info().project.name !== "desktop-chromium",
      "The nav rail is desktop-only; mobile uses the bottom tab bar.",
    );
    test.setTimeout(60_000);
    await isolateSettings(page);
    await page.goto("/");

    const toggle = page.getByTestId("history-sidebar-btn");
    await expect(toggle).toBeVisible();
    await expect(toggle).toHaveAttribute("aria-pressed", "false");

    const responsePromise = page.waitForResponse(
      (res) => res.url().includes("/api/v1/conversations") && res.status() === 200,
      { timeout: 15_000 },
    );
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-pressed", "true");

    const panel = page.getByTestId("conversation-history-panel");
    await expect(panel).toBeVisible();

    // The endpoint must still answer with a bare array; the client parses both
    // shapes, so assert the wire format here rather than trusting the UI.
    const payload = await (await responsePromise).json();
    expect(Array.isArray(payload)).toBe(true);
    test.skip(payload.length === 0, "This backend has no saved threads to list.");

    const rows = panel.getByTestId("conversation-row");
    await expect(rows.first()).toBeVisible();
    expect(await rows.count()).toBe(payload.length);
    // A row that renders a blank label is a parse failure, not an empty account.
    const firstTitle = (await rows.first().innerText()).trim();
    expect(firstTitle.length).toBeGreaterThan(0);

    // Selecting a thread loads it and dismisses the overlay.
    await rows.first().click();
    await expect(panel).toHaveCount(0);
    await expect(toggle).toHaveAttribute("aria-pressed", "false");

    await page.screenshot({ path: "test-results/history-panel.png", fullPage: false });
  });

  test("the top-bar search control opens the same panel", async ({ page }) => {
    test.skip(
      test.info().project.name !== "desktop-chromium",
      "The search control lives in the desktop top bar.",
    );
    test.setTimeout(60_000);
    await isolateSettings(page);
    await page.goto("/");

    await page.getByRole("button", { name: /Search/ }).first().click();
    const panel = page.getByTestId("conversation-history-panel");
    await expect(panel).toBeVisible();
    await expect(panel.getByTestId("conversation-row").first()).toBeVisible();
  });
});
