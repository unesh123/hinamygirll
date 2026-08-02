import { expect, test } from "@playwright/test";

test("fits the small mobile viewport and completes a mock text turn", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByLabel("Voice status")).toContainText("Voice ready");
  const shell = page.locator("main");
  const box = await shell.boundingBox();
  expect(box?.width).toBeLessThanOrEqual(page.viewportSize()!.width);

  await page.getByLabel("Type a message").fill("Aaja mood ali off cha");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.getByText(/heavy feel bhairako/)).toBeVisible({
    timeout: 5000,
  });
  await expect(page.locator('[data-emotion="concerned"]')).toBeVisible();
});

test("supports simulated voice interruption and accessibility modes", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: /simulate microphone listening/i })
    .click();
  const stopButton = page.getByRole("button", {
    name: /Stop current turn/,
  });
  await expect(stopButton).toBeVisible();
  await stopButton.click();
  await expect(page.getByLabel("Type a message")).toBeEnabled();

  await page.getByRole("button", { name: /Text only/ }).click();
  await expect(
    page.getByText(
      "Avatar motion is paused. Conversation controls still work.",
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: /Reduced motion off/ }).click();
  await expect(
    page.getByRole("button", { name: /Reduced motion on/ }),
  ).toHaveAttribute("aria-pressed", "true");
});

test("shows a graceful WebGL message without losing chat", async ({ page }) => {
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
  await expect(page.getByText(/WebGL is unavailable/)).toBeVisible();
  await expect(page.getByLabel("Type a message")).toBeEnabled();
});

test("loads the production PWA shell while offline after first visit", async ({
  page,
  context,
}) => {
  await page.goto("/");
  await page.evaluate(async () => {
    if (!("serviceWorker" in navigator))
      throw new Error("Service worker unsupported");
    await navigator.serviceWorker.ready;
  });
  await context.setOffline(true);
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByLabel("Voice status")).toContainText("Voice ready");
  await expect(page.getByLabel("Type a message")).toBeEnabled();
});

test("proxies safe provider metadata without making provider calls", async ({
  page,
}) => {
  await page.goto("/");
  const status = await page.evaluate(async () => {
    const response = await fetch("/api/v1/providers");
    return { ok: response.ok, providers: await response.json() };
  });
  expect(status.ok).toBe(true);
  expect(status.providers[0].id).toBe("mock");
  await page.getByText("Advanced voice settings").click();
  await expect(page.getByLabel("Provider mode")).toHaveValue("mock");
  await expect(page.getByLabel("Provider mode")).toContainText(
    "Groq fast brain",
  );
  await expect(page.getByLabel("Provider mode")).toContainText(
    "Microsoft voice + OpenAI brain",
  );
});

test("runs a synthetic mock WebSocket turn without microphone or provider calls", async ({
  page,
}) => {
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
  await page.getByRole("button", { name: "Talk to Hinaa" }).click();
  await expect(page.getByText(/Microphone permission denied/)).toBeVisible();
  await expect(page.getByLabel("Type a message")).toBeEnabled();
});
