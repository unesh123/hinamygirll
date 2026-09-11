import { expect, test } from "@playwright/test";
import { isolateSettings } from "./helpers";

test("keeps full-body avatar framing readable with captions enabled", async ({
  page,
}, testInfo) => {
  await isolateSettings(page);
  await page.goto("/");

  await page.getByRole("button", { name: "Talk", exact: true }).click();
  await page.getByLabel("Avatar framing").selectOption("full");

  const stage = page.getByTestId("hinaa-stage");
  await expect(stage).toBeVisible();
  await expect(stage.locator("canvas").first()).toBeVisible({ timeout: 15000 });

  const caption = page.getByTestId("hinaa-caption");
  await expect(caption).toBeVisible();

  if (testInfo.project.name === "desktop-chromium") {
    const stageBox = await stage.boundingBox();
    const captionBox = await caption.boundingBox();
    expect(stageBox).toBeTruthy();
    expect(captionBox).toBeTruthy();
    expect(captionBox!.x).toBeGreaterThan(stageBox!.x + stageBox!.width * 0.58);
    expect(captionBox!.y + captionBox!.height).toBeLessThan(stageBox!.y + stageBox!.height * 0.45);
  }
});
