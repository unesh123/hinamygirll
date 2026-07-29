import { expect, test } from "@playwright/test";

test("fits the small mobile viewport and completes a mock text turn", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByLabel("Provider mode")).toHaveValue("mock");
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
  await expect(page.getByText("Interrupted")).toBeVisible();

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
  await expect(page.getByLabel("Provider mode")).toHaveValue("mock");
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
  await expect(page.getByLabel("Provider mode")).toHaveValue("mock");
});
