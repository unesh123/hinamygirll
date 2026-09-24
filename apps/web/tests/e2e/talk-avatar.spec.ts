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
    const canvasBox = await stage.locator("canvas").first().boundingBox();
    const placement = await caption.evaluate((el) => {
      const s = getComputedStyle(el);
      return { classes: el.className, top: s.top, bottom: s.bottom, left: s.left, right: s.right };
    });
    console.log(
      `caption placement — ${JSON.stringify(placement)}; stage ${JSON.stringify(stageBox)}; ` +
        `caption ${JSON.stringify(captionBox)}; canvas ${JSON.stringify(canvasBox)}`
    );
    expect(stageBox).toBeTruthy();
    expect(captionBox).toBeTruthy();
    expect(canvasBox).toBeTruthy();

    // The framing control has to actually change the presentation.
    expect(placement.classes).toContain("hinaa-caption--full");

    // "Readable" means the caption never covers her face. In full-body framing
    // the face sits in the upper middle of the canvas, so the caption has to
    // clear that column and stay inside the stage.
    expect(captionBox!.x, "the caption covers her face").toBeGreaterThan(canvasBox!.x + canvasBox!.width * 0.5);
    expect(captionBox!.y, "the caption sits below her face").toBeLessThan(canvasBox!.y + canvasBox!.height * 0.45);
    expect(captionBox!.x + captionBox!.width).toBeLessThanOrEqual(stageBox!.x + stageBox!.width + 1);
  }
});

test("persists the voice language chosen on the talk toolbar", async ({ page }) => {
  await isolateSettings(page);
  await page.goto("/");

  await page.getByRole("button", { name: "Talk", exact: true }).click();
  const select = page.getByLabel("Voice language");
  await expect(select).toBeVisible();
  // The picker is disabled while a live session holds the microphone.
  await expect(select).toBeEnabled();
  await select.selectOption("ne-NP");

  // Reading the durable record is what proves the control is wired: the value
  // also has to survive the reload, and settings are re-seeded on every load.
  const stored = await page.evaluate(() => {
    const raw = localStorage.getItem("hinaa_settings_v1");
    if (!raw) return null;
    try {
      return JSON.parse(raw)?.language?.activePolicy ?? null;
    } catch {
      return "unparseable";
    }
  });
  console.log(`language control — selected "ne-NP", persisted ${JSON.stringify(stored)}`);
  expect(stored, "the toolbar language never reaches the persisted settings").toBe("ne-NP");
});
