import { expect, test } from "@playwright/test";
import { isolateSettings, pinMockSetup } from "./helpers";

/**
 * core-states.spec.ts — end-to-end coverage of the reactive state machine:
 * the crystalline core indicator and the avatar must both follow the same
 * real events (idle → speaking → idle) through a full mock turn.
 *
 * Determinism strategy (shared with conversation.spec.ts): pin provider →
 * "Demo" (fixed 260ms mock delays) and avatar style → "2D avatar"
 * (procedural, always mounted) via pinMockSetup.
 *
 * Mock brain mapping used here: /mood|off|sad/ → emotion "concerned".
 */

test("core indicator + avatar drive through idle → speaking → idle", async ({
  page,
}) => {
  await isolateSettings(page);
  await page.goto("/");
  await pinMockSetup(page);

  // Fresh stage: the core breathes white idle and the iris ring is quiet.
  const core = page.locator(".core-indicator");
  await expect(core).toHaveAttribute("data-core", "idle");
  await expect(core).toHaveAttribute("data-iris-ring", "quiet");

  // Send a message the mock brain maps to a concerned reply.
  await page.getByLabel("Type a message").fill("mood off today");
  await page.getByRole("button", { name: "Send message" }).click();

  const avatar = page.locator('[data-engine="procedural-avatar-v1"]');
  await expect(avatar).toHaveAttribute("data-state", "speaking", {
    timeout: 8000,
  });
  await expect(avatar).toHaveAttribute("data-emotion", "concerned");

  // While she speaks, the core shows blue speaking.
  await expect(core).toHaveAttribute("data-core", "speaking");

  // The header status pill tracks the same state machine.
  await expect(page.locator(".header-status")).toHaveAttribute(
    "data-state",
    "speaking",
  );

  // After the turn she returns to idle and the core settles back to white.
  await expect(avatar).toHaveAttribute("data-state", "idle", { timeout: 8000 });
  await expect(core).toHaveAttribute("data-core", "idle");
  await expect(core).toHaveAttribute("data-iris-ring", "quiet");
});

test("core shows red failure when the voice session cannot start", async ({
  page,
}) => {
  await isolateSettings(page);
  await page.goto("/");
  await pinMockSetup(page);

  const core = page.locator(".core-indicator");
  await expect(core).toHaveAttribute("data-core", "idle");

  // Tap the stage background (top-left, clear of the avatar and panels) to
  // start the voice session. The Playwright mobile emulation has no working
  // microphone, so getUserMedia fails and the app must honestly show the red
  // failure state — never a fake "listening".
  await page.locator(".hinaa-stage").click({ position: { x: 24, y: 120 } });

  await expect(core).toHaveAttribute("data-core", "failure", {
    timeout: 8000,
  });
  await expect(page.locator(".stage-status-bar")).toContainText(
    /reconnect/i,
  );
});
