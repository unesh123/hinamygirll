import { expect, test } from "@playwright/test";
import { isolateSettings, pinMockSetup } from "./helpers";

/**
 * voice.spec.ts — end-to-end hands-free voice-flow coverage.
 *
 * Both tests start the live session exactly like a user: tap the stage. They
 * stub navigator.mediaDevices.getUserMedia so the flow is deterministic with
 * no real hardware:
 *
 *   - Granted  → silent audio track → AudioContext + worklet + realtime
 *                session.ready → status "listening" → listening indicator.
 *   - Denied   → NotAllowedError → safe error state with a recoverable hint,
 *                never a listening UI, text composer stays available.
 *
 * The granted test still connects to the real mock realtime backend (the API
 * is a required webServer dependency, and the preview /api proxy is already
 * proven by the synthetic-WebSocket spec), which is what makes the
 * session.ready → listening transition genuine.
 */

function stubGetUserMedia(page: import("@playwright/test").Page, denied: boolean) {
  return page.addInitScript(
    ({ denied }) => {
      Object.defineProperty(navigator, "mediaDevices", {
        configurable: true,
        value: {
          getUserMedia: async () => {
            if (denied) {
              throw new DOMException("Permission denied", "NotAllowedError");
            }
            // MediaStreamAudioDestinationNode always exposes an audio track.
            // It produces silence, so the VAD start threshold is never tripped
            // and the session simply stays in the listening state.
            const ctx = new AudioContext();
            return ctx.createMediaStreamDestination().stream;
          },
        },
      });
    },
    { denied },
  );
}

test("grants the mic and shows the listening indicator after tapping the stage", async ({
  page,
}) => {
  await isolateSettings(page);
  await stubGetUserMedia(page, false);
  await page.goto("/");
  await pinMockSetup(page);

  // Start the hands-free session with a real tap on the stage.
  await page.locator("main.hinaa-stage").click();

  // The session moves connecting → listening once the mock realtime backend
  // answers session.ready; the listening indicator replaces the tap hint.
  const listening = page.locator(".listening-indicator");
  await expect(listening).toBeVisible({ timeout: 15000 });
  await expect(listening).toContainText("Listening…");

  // The avatar and the header pill both agree she is listening.
  await expect(
    page.locator('[data-engine="procedural-avatar-v1"]'),
  ).toHaveAttribute("data-state", "listening");
  await expect(page.locator(".header-status")).toHaveAttribute(
    "data-state",
    "listening",
  );

  // The text composer is replaced by the live voice controls while active.
  await expect(page.getByLabel("Type a message")).toBeHidden();
});

test("denies the mic and renders error handling without a listening indicator", async ({
  page,
}) => {
  await isolateSettings(page);
  await stubGetUserMedia(page, true);
  await page.goto("/");

  await page.locator("main.hinaa-stage").click();

  // Safe error state: a recoverable hint replaces the listening UI.
  const errorHint = page.locator(".error-hint");
  await expect(errorHint).toBeVisible({ timeout: 10000 });
  await expect(errorHint).toContainText("Microphone permission denied");
  await expect(errorHint).toContainText("tap to reconnect");

  // The denied path never shows a listening indicator.
  await expect(page.locator(".listening-indicator")).toHaveCount(0);

  // The header reflects the error and the text composer is available again.
  await expect(page.locator(".header-status")).toHaveAttribute(
    "data-state",
    "error",
  );
  await expect(page.getByLabel("Type a message")).toBeEnabled();
});
