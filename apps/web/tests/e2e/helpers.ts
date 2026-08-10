import { expect, type Page } from "@playwright/test";

/**
 * Settings are persisted to localStorage under hinaa_settings_v1. Because
 * Playwright reuses a browser context across tests in a worker, one test that
 * pins the provider or avatar style would leak into the next. Running this
 * before every page load restores default settings for each test.
 */
export async function isolateSettings(page: Page): Promise<void> {
  await page.addInitScript(() => {
    try {
      localStorage.removeItem("hinaa_settings_v1");
    } catch {
      // Storage may be unavailable — the app falls back to defaults anyway.
    }
  });
}

/**
 * Pin provider → Demo (MockConversationProvider, deterministic, offline) and
 * avatar style → 2D (ProceduralAvatar, always mounted, no remote VRM fetch).
 * This makes text and voice turns deterministic and network-free, so specs
 * never depend on a live provider or the 3D model pipeline.
 */
export async function pinMockSetup(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Settings" }).click();
  const dialog = page.getByTestId("settings-dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("AI provider").selectOption({ label: "Demo" });
  await dialog.getByLabel("Avatar style").selectOption({ label: "2D avatar" });
  await dialog.getByRole("button", { name: "Close settings" }).click();
  await expect(dialog).not.toBeVisible();
}

/**
 * Switch the active companion through the settings dialog and close it. The
 * companion buttons expose the name (e.g. "Hinaa Warm & playful"), so the
 * regex matches by name alone.
 */
export async function switchCompanion(
  page: Page,
  name: string,
): Promise<void> {
  await page.getByRole("button", { name: "Settings" }).click();
  const dialog = page.getByTestId("settings-dialog");
  await dialog.getByRole("button", { name: new RegExp(name) }).click();
  await dialog.getByRole("button", { name: "Close settings" }).click();
  await expect(dialog).not.toBeVisible();
}
