import { chromium } from "@playwright/test";
import { spawn } from "node:child_process";
import path from "node:path";
import fs from "node:fs";

const ARTIFACT_PATH = "C:\\Users\\unesh\\.gemini\\antigravity\\brain\\e241b5a6-dc0c-4f32-bacf-eb53db6cb5c7\\hina_split_card_walk.png";

// 1. Start vite preview server on port 5173
console.log("Starting vite preview on port 5173...");
const preview = spawn("npx", ["vite", "preview", "--port", "5173", "--strictPort"], {
  cwd: path.resolve(process.cwd(), "apps", "web"),
  shell: true,
  stdio: "pipe",
});

preview.stdout.on("data", (data) => console.log(`[preview]: ${data}`));
preview.stderr.on("data", (data) => console.error(`[preview-err]: ${data}`));

// Wait for preview server to be ready
await new Promise((resolve) => setTimeout(resolve, 3000));

try {
  console.log("Launching Chromium...");
  const browser = await chromium.launch({
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });

  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });

  // Mock settings so it starts cleanly in work mode
  await page.addInitScript(() => {
    try {
      localStorage.setItem(
        "hinaa_settings_v1",
        JSON.stringify({
          _version: 1,
          appearance: { theme: "dark", motion: "system", avatarVisible: false },
          provider: { preferredMode: "mock" },
        })
      );
    } catch (e) {}
  });

  console.log("Navigating to http://127.0.0.1:5173/...");
  await page.goto("http://127.0.0.1:5173/", { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(1000);

  // Find the composer textarea
  console.log("Locating chat composer textarea...");
  const textarea = page.locator("textarea").first();
  await textarea.waitFor({ timeout: 10000 });

  // Type "split 2400 between 3"
  console.log("Typing 'split 2400 between 3' into composer...");
  await textarea.fill("split 2400 between 3");

  // Wait for HinaSurface to morph and SplitCard to appear (~220ms spring)
  console.log("Waiting for SplitCard to morph in...");
  await page.waitForTimeout(800);

  // Take screenshot
  console.log(`Saving screenshot to ${ARTIFACT_PATH}...`);
  await page.screenshot({ path: ARTIFACT_PATH, fullPage: false });

  console.log("SUCCESS! Screenshot captured.");
  await browser.close();
} catch (err) {
  console.error("Failed to capture screenshot:", err);
} finally {
  preview.kill();
  process.exit(0);
}
