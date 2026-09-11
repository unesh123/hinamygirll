import { expect, test } from "@playwright/test";
import { isolateSettings } from "./helpers";

test("chat companion keeps avatar visible while switching camera and VRM model", async ({
  page,
}) => {
  await isolateSettings(page);
  await page.addInitScript(() => {
    for (const key of [
      "hinaa.session.active.v1",
      "hinaa-active-conversation-id",
      "hinaa-sakura-view",
      "hinaa.avatar-model",
      "hinaa.avatar-camera.v1",
    ]) {
      localStorage.removeItem(key);
    }
  });
  await page.goto("/");

  // Mobile Work mode intentionally uses a chat-first layout with a dedicated
  // avatar tab; the desktop companion panel is not rendered at phone widths.
  if (test.info().project.name === "small-android") {
    await expect(page.getByTestId("mobile-mode-switcher")).toBeVisible();
    await page.getByTestId("mobile-tab-avatar").click();
    const mobileAvatar = page.getByTestId("mobile-avatar-screen");
    await expect(mobileAvatar).toBeVisible();
    await expect(mobileAvatar.locator("canvas").first()).toBeVisible({ timeout: 15_000 });
    await page.getByTestId("mobile-back-to-chat").click();
    await expect(page.getByTestId("work-composer")).toBeVisible();
    return;
  }

  const panel = page.getByTestId("work-companion-panel");
  const stage = page.getByTestId("work-companion-stage");
  await expect(panel).toBeVisible();
  await expect(stage.locator("canvas").first()).toBeVisible({ timeout: 15_000 });

  await page.getByLabel("Close-up Camera").click();
  await expect(page.getByLabel(/Change avatar camera from closeup/i)).toBeVisible();
  await expect(stage.locator("canvas").first()).toBeVisible();

  await page.getByRole("button", { name: /Switch 3D Avatar Model/i }).click();
  await page.getByText("Sakura Student (Sample E)", { exact: true }).click();

  await expect(page.getByRole("button", { name: /Switch 3D Avatar Model/i })).toContainText("Sakura");
  await expect(page.getByLabel(/Change avatar camera from closeup/i)).toBeVisible();
  await expect(stage.locator("canvas").first()).toBeVisible({ timeout: 15_000 });
});
