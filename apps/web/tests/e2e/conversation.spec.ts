import { expect, test } from "@playwright/test";
import {
  isolateSettings,
  pinMockSetup,
  switchCompanion,
} from "./helpers";

/**
 * conversation.spec.ts — end-to-end text conversation coverage.
 *
 * Determinism strategy: pin provider → "Demo" (mock brain, fixed 260ms
 * delays) and avatar style → "2D avatar" (procedural, always mounted) via
 * the shared pinMockSetup helper, so turns never touch a live provider or
 * the 3D model pipeline.
 *
 * The mock brain maps fixed keywords to fixed emotions:
 *   /mood|off|sad|दुख|मन/ → emotion "concerned" · text contains "slow down"
 *   /assignment|बुझ|explain/ → emotion "thinking" · gesture "explain"
 */

test("sends a text message and renders user + assistant chat bubbles", async ({
  page,
}) => {
  await isolateSettings(page);
  await page.goto("/");
  await pinMockSetup(page);

  const composer = page.getByLabel("Type a message");
  await expect(composer).toBeEnabled();

  // Send a message the mock brain maps to a fixed concerned reply.
  await composer.fill("Aaja mood ali off cha");
  await page.getByRole("button", { name: "Send message" }).click();

  const transcript = page.getByTestId("transcript");
  await expect(transcript).toBeVisible();

  // The user's bubble lands in the log…
  await expect(
    transcript.locator('article[data-role="user"]'),
  ).toContainText("Aaja mood ali off cha");

  // …and the assistant's streamed reply bubble follows with mock text.
  const assistantBubbles = transcript.locator('article[data-role="assistant"]');
  await expect(assistantBubbles.last()).toContainText(/Mock mode हो.*slow down/, {
    timeout: 8000,
  });

  // Both bubbles coexist in the conversation log.
  await expect(transcript.locator('article[data-role="user"]')).toHaveCount(1);
});

test("drives the avatar to the planned emotion during the reply", async ({
  page,
}) => {
  await isolateSettings(page);
  await page.goto("/");
  await pinMockSetup(page);

  await page.getByLabel("Type a message").fill("mood off today");
  await page.getByRole("button", { name: "Send message" }).click();

  // The mock plan for "mood/off" is emotion: concerned — the procedural
  // avatar must carry that emotion while she speaks the reply.
  const avatar = page.locator('[data-engine="procedural-avatar-v1"]');
  await expect(avatar).toBeVisible();
  await expect(avatar).toHaveAttribute("data-state", "speaking", {
    timeout: 8000,
  });
  await expect(avatar).toHaveAttribute("data-emotion", "concerned");
  // After the turn, she returns to idle (mood stays on her face until the
  // next plan, matching the app's plan-fallback behaviour).
  await expect(avatar).toHaveAttribute("data-state", "idle", {
    timeout: 8000,
  });

  // The reply text streams into the transcript as well.
  await expect(page.getByTestId("transcript")).toContainText("slow down", {
    timeout: 8000,
  });
});

test("keeps the greeting visible before any message is sent", async ({
  page,
}) => {
  await isolateSettings(page);
  await page.goto("/");

  // Hinaa's greeting is the first assistant bubble in the fresh log.
  await expect(page.getByTestId("transcript")).toContainText(
    "Hinaa ready cha",
  );
  await expect(
    page.getByTestId("transcript").locator('article[data-role="assistant"]'),
  ).toHaveCount(1);
});

test("switches to Hiro and greets with his happy + calm personas", async ({
  page,
}) => {
  await isolateSettings(page);
  await page.goto("/");
  await pinMockSetup(page);

  // Switch companion to Hiro inside the settings dialog.
  await switchCompanion(page, "Hiro");

  const transcript = page.getByTestId("transcript");

  // The transcript resets to Hiro's own greeting — Hinaa's is gone.
  await expect(transcript).toContainText("Hiro ready cha");
  await expect(transcript).not.toContainText("Hinaa ready cha");
  await expect(
    transcript.locator('article[data-role="assistant"]'),
  ).toHaveCount(1);

  // The profile card reflects the active companion.
  await expect(page.locator(".companion-profile-card")).toHaveAttribute(
    "data-companion",
    "hiro",
  );

  // Send a message the mock brain maps to a happy reply (hello → happy/wave).
  await page.getByLabel("Type a message").fill("hello");
  await page.getByRole("button", { name: "Send message" }).click();

  // The procedural avatar carries the happy face preset while he speaks
  // (mock hello plan: emotion happy → facePreset soft_smile).
  const avatar = page.locator('[data-engine="procedural-avatar-v1"]');
  await expect(avatar).toBeVisible();
  await expect(avatar).toHaveAttribute("data-state", "speaking", {
    timeout: 8000,
  });
  await expect(avatar).toHaveAttribute("data-emotion", "soft_smile");
  // The profile card surfaces the primary emotion label while speaking.
  await expect(page.locator(".companion-profile-card")).toContainText(
    /Speaking · happy/,
  );

  // And the streamed reply lands in the log.
  await expect(
    transcript.locator('article[data-role="assistant"]').last(),
  ).toContainText(/Namaste! Mock mode/, { timeout: 8000 });

  // ── Calm & helpful persona ─────────────────────────────────────────────
  // Send a task-y message — the mock maps /assignment|बुझ|explain/ to the
  // thinking emotion + explain gesture (Hiro's helpful mode).
  await page.getByLabel("Type a message").fill("explain my assignment");
  await page.getByRole("button", { name: "Send message" }).click();

  await expect(avatar).toHaveAttribute("data-state", "speaking", {
    timeout: 8000,
  });
  // The gesture cue is the shorter-lived one (~1.7s window), so assert it
  // first for maximum margin before the longer emotion cue.
  await expect(avatar).toHaveAttribute("data-gesture", "explain");
  await expect(avatar).toHaveAttribute("data-emotion", "thinking");
  // The profile card surfaces the calm/helpful state while he works it out.
  await expect(page.locator(".companion-profile-card")).toContainText(
    /Speaking · thinking/,
  );

  // And the task-y reply streams into the log.
  await expect(
    transcript.locator('article[data-role="assistant"]').last(),
  ).toContainText(/Mock modeले assignment साँच्चै बुझेको होइन/, {
    timeout: 8000,
  });
});

test("switches Hinaa → Hiro → Hinaa mid-conversation and resets each log", async ({
  page,
}) => {
  // Two full turns plus two companion switches — needs more than the 30s
  // default when the suite runs fully parallel on a loaded machine.
  test.setTimeout(60_000);
  await isolateSettings(page);
  await page.goto("/");
  await pinMockSetup(page);

  const transcript = page.getByTestId("transcript");
  const composer = page.getByLabel("Type a message");
  const send = page.getByRole("button", { name: "Send message" });

  // Session 1 — Hinaa: greeting, then one real turn so the log is non-empty.
  await expect(transcript).toBeVisible();
  await expect(transcript).toContainText("Hinaa ready cha");
  await composer.fill("hello");
  await send.click();
  await expect(
    transcript.locator('article[data-role="assistant"]').last(),
  ).toContainText(/Namaste! Mock mode/, { timeout: 8000 });
  await expect(transcript.locator('article[data-role="user"]')).toHaveCount(1);
  await expect(
    transcript.locator('article[data-role="assistant"]'),
  ).toHaveCount(2);

  // Switch to Hiro mid-conversation — the log resets to his own greeting,
  // and Hinaa's greeting + the exchanged messages are gone.
  await switchCompanion(page, "Hiro");

  await expect(transcript).toContainText("Hiro ready cha");
  await expect(transcript).not.toContainText("Hinaa ready cha");
  await expect(transcript.locator('article[data-role="user"]')).toHaveCount(0);
  await expect(
    transcript.locator('article[data-role="assistant"]'),
  ).toHaveCount(1);
  await expect(page.locator(".companion-profile-card")).toHaveAttribute(
    "data-companion",
    "hiro",
  );

  // Session 2 — Hiro: another turn so his log has content to clear.
  await composer.fill("hello");
  await send.click();
  await expect(
    transcript.locator('article[data-role="assistant"]').last(),
  ).toContainText(/Namaste! Mock mode/, { timeout: 8000 });
  await expect(
    transcript.locator('article[data-role="assistant"]'),
  ).toHaveCount(2);

  // Switch back to Hinaa — Hiro's greeting and messages vanish, hers return.
  await switchCompanion(page, "Hinaa");

  await expect(transcript).toContainText("Hinaa ready cha");
  await expect(transcript).not.toContainText("Hiro ready cha");
  await expect(transcript.locator('article[data-role="user"]')).toHaveCount(0);
  await expect(
    transcript.locator('article[data-role="assistant"]'),
  ).toHaveCount(1);
  await expect(page.locator(".companion-profile-card")).toHaveAttribute(
    "data-companion",
    "hinaa",
  );
});

test("re-selecting the active companion keeps the transcript intact", async ({
  page,
}) => {
  await isolateSettings(page);
  await page.goto("/");
  await pinMockSetup(page);

  const transcript = page.getByTestId("transcript");

  // Build a non-empty conversation first: greeting + one full turn.
  await expect(transcript).toContainText("Hinaa ready cha");
  await page.getByLabel("Type a message").fill("hello");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(
    transcript.locator('article[data-role="assistant"]').last(),
  ).toContainText(/Namaste! Mock mode/, { timeout: 8000 });
  await expect(transcript.locator('article[data-role="user"]')).toHaveCount(1);
  await expect(
    transcript.locator('article[data-role="assistant"]'),
  ).toHaveCount(2);

  // Re-select the already-active Hinaa — this must be a no-op.
  await switchCompanion(page, "Hinaa");

  // Nothing reset: her greeting is still the first bubble, and both the
  // user's message and the reply are still in the log.
  await expect(transcript).toContainText("Hinaa ready cha");
  await expect(transcript.locator('article[data-role="user"]')).toHaveCount(1);
  await expect(
    transcript.locator('article[data-role="assistant"]'),
  ).toHaveCount(2);
  await expect(page.locator(".companion-profile-card")).toHaveAttribute(
    "data-companion",
    "hinaa",
  );
});
