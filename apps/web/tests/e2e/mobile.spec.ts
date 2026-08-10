import { expect, test } from "@playwright/test";
import { isolateSettings } from "./helpers";

test("fits the small mobile viewport and completes a mock text turn", async ({
  page,
}) => {
  await isolateSettings(page);
  await page.goto("/");
  const shell = page.locator("main");
  const box = await shell.boundingBox();
  expect(box?.width).toBeLessThanOrEqual(page.viewportSize()!.width);

  // Pin provider to Demo (mock, offline) and avatar to the 2D procedural
  // engine (no remote VRM fetch) so the turn is deterministic.
  await page.getByRole("button", { name: "Settings" }).click();
  await page
    .getByTestId("settings-dialog")
    .getByLabel("AI provider")
    .selectOption({ label: "Demo" });
  await page
    .getByTestId("settings-dialog")
    .getByLabel("Avatar style")
    .selectOption({ label: "2D avatar" });
  await page
    .getByTestId("settings-dialog")
    .getByRole("button", { name: "Close settings" })
    .click();

  await page.getByLabel("Type a message").fill("Aaja mood ali off cha");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByTestId("transcript")).toContainText("slow down", {
    timeout: 8000,
  });
  // The avatar carries the planned emotion while she speaks the reply.
  const avatar = page.locator('[data-engine="procedural-avatar-v1"]');
  await expect(avatar).toHaveAttribute("data-state", "speaking", {
    timeout: 8000,
  });
  await expect(avatar).toHaveAttribute("data-emotion", "concerned");
});

test("supports text-only avatar mode and reduced-motion settings", async ({
  page,
}) => {
  await isolateSettings(page);
  await page.goto("/");

  // Pin the avatar to the 2D procedural engine so the default VRM fetch can't
  // stall the stage in the test environment.
  await page.getByRole("button", { name: "Settings" }).click();
  await page
    .getByTestId("settings-dialog")
    .getByLabel("Avatar style")
    .selectOption({ label: "2D avatar" });
  await page
    .getByTestId("settings-dialog")
    .getByRole("button", { name: "Close settings" })
    .click();

  const avatar = page.locator('[data-engine="procedural-avatar-v1"]').first();
  await expect(avatar).toBeVisible({ timeout: 10000 });

  // Reduced motion: select it in settings and the avatar reports it.
  await page.getByRole("button", { name: "Settings" }).click();
  await page
    .getByTestId("settings-dialog")
    .getByLabel("Motion")
    .selectOption({ label: "Reduced motion" });
  await page
    .getByTestId("settings-dialog")
    .getByRole("button", { name: "Close settings" })
    .click();
  // The avatar is still visible here — the text-only step comes after, so the
  // reduced-motion attribute is readable before it swaps to the fallback card.
  await expect(avatar).toHaveAttribute("data-reduced-motion", "true");

  // Text-only mode: hide the avatar in Appearance settings. The row label
  // wraps the visually-hidden input, so clicking the label toggles it the way
  // a real user (or keyboard) would, and React's onChange fires.
  await page.getByRole("button", { name: "Settings" }).click();
  await page
    .getByTestId("settings-dialog")
    .getByText("Show avatar")
    .first()
    .click();
  await page
    .getByTestId("settings-dialog")
    .getByRole("button", { name: "Close settings" })
    .click();
  await expect(
    page.getByText(
      "Avatar motion is paused. Conversation controls still work.",
    ),
  ).toBeVisible();

  await expect(page.getByLabel("Type a message")).toBeEnabled();
});

test("falls back to the procedural avatar when WebGL is unavailable", async ({
  page,
}) => {
  await isolateSettings(page);
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (
      type: string,
      ...args: unknown[]
    ) {
      if (type.startsWith("webgl") || type === "experimental-webgl")
        return null;
      return original.call(this, type as "2d", ...args);
    } as typeof HTMLCanvasElement.prototype.getContext;
  });
  await page.goto("/");

  // Pin the avatar to the 2D procedural engine (no WebGL needed) so the
  // conversation stays usable on WebGL-less devices.
  await page.getByRole("button", { name: "Settings" }).click();
  await page
    .getByTestId("settings-dialog")
    .getByLabel("Avatar style")
    .selectOption({ label: "2D avatar" });
  await page
    .getByTestId("settings-dialog")
    .getByRole("button", { name: "Close settings" })
    .click();

  await expect(
    page.locator('[data-engine="procedural-avatar-v1"]').first(),
  ).toBeVisible({ timeout: 10000 });
  await expect(page.getByLabel("Type a message")).toBeEnabled();
});

test("keeps the shell usable when the backend is unreachable", async ({
  page,
}) => {
  await isolateSettings(page);
  // Block the provider-status fetch so the app renders without backend metadata.
  await page.route("**/api/v1/providers", (route) => route.abort());
  await page.goto("/");
  await expect(page.locator("main.hinaa-stage")).toBeVisible();
  await expect(page.getByLabel("Type a message")).toBeEnabled();
  // The header status pill shows the idle state even without provider info.
  await expect(page.locator(".header-status")).toContainText("Ready");
});

test("proxies safe provider metadata without making provider calls", async ({
  page,
}) => {
  await isolateSettings(page);
  await page.goto("/");
  const status = await page.evaluate(async () => {
    const response = await fetch("/api/v1/providers");
    return { ok: response.ok, providers: await response.json() };
  });
  expect(status.ok).toBe(true);
  expect(status.providers[0].id).toBe("mock");
  // The settings dialog exposes the provider picker with the safe demo option.
  await page.getByRole("button", { name: "Settings" }).click();
  const provider = page
    .getByTestId("settings-dialog")
    .getByLabel("AI provider");
  await expect(provider).toBeVisible();
  await expect(provider).toContainText("Demo");
  await expect(provider).toContainText("CX Gateway");
  await expect(provider).toContainText("Gemini Live");
});

test("runs a synthetic mock WebSocket turn without microphone or provider calls", async ({
  page,
}) => {
  await isolateSettings(page);
  await page.goto("/");
  const eventTypes = await page.evaluate(
    () =>
      new Promise<string[]>((resolve, reject) => {
        const types: string[] = [];
        const protocol = location.protocol === "https:" ? "wss:" : "ws:";
        const socket = new WebSocket(
          `${protocol}//${location.host}/api/v1/realtime`,
        );
        const timeout = window.setTimeout(
          () => reject(new Error("mock realtime timeout")),
          8000,
        );
        socket.onopen = () =>
          socket.send(
            JSON.stringify({
              type: "session.hello",
              protocolVersion: "1.0",
              sessionId: "mobile-e2e",
              companionId: "hinaa",
              providerMode: "mock",
              generation: 1,
              language: "mixed",
              languageMode: "fixed-ne-NP",
              calibration: "natural",
            }),
          );
        socket.onerror = () => reject(new Error("mock realtime socket error"));
        socket.onmessage = (message) => {
          const event = JSON.parse(message.data as string) as { type: string };
          types.push(event.type);
          if (event.type === "session.ready") {
            socket.send(JSON.stringify({ type: "audio.start", generation: 1 }));
          } else if (event.type === "audio.started") {
            const pcm = new Int16Array(320);
            pcm.fill(2000);
            socket.send(
              JSON.stringify({
                type: "audio.frame",
                sequence: 0,
                generation: 1,
                capturedAtMs: 20,
                byteLength: pcm.byteLength,
              }),
            );
            socket.send(pcm.buffer);
          } else if (event.type === "stt.partial") {
            socket.send(
              JSON.stringify({
                type: "audio.commit",
                generation: 1,
                endedAtMs: 40,
                mockTranscript: "नमस्ते हिना।",
              }),
            );
          } else if (event.type === "turn.complete") {
            window.clearTimeout(timeout);
            socket.close();
            resolve(types);
          }
        };
      }),
  );
  expect(eventTypes).toContain("assistant.text.delta");
  expect(eventTypes).toContain("assistant.plan");
  expect(eventTypes).toContain("tts.audio");
  expect(eventTypes.at(-1)).toBe("turn.complete");
});

test("keeps text fallback available when live microphone permission is denied", async ({
  page,
}) => {
  await isolateSettings(page);
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: () =>
          Promise.reject(
            new DOMException("Denied for test", "NotAllowedError"),
          ),
      },
    });
  });
  await page.goto("/");
  // Tap the stage to start a live session — the mic request fails safely.
  await page.locator("main.hinaa-stage").click();
  await expect(page.getByText(/permission denied/i)).toBeVisible({
    timeout: 8000,
  });
  await expect(page.getByLabel("Type a message")).toBeEnabled();
});
