import { chromium } from "@playwright/test";
import { spawn } from "node:child_process";
import path from "node:path";
import fs from "node:fs";

const OUT_DIR = "C:\\Users\\unesh\\.gemini\\antigravity\\brain\\e241b5a6-dc0c-4f32-bacf-eb53db6cb5c7";

try {

  console.log("Launching Chromium...");
  const browser = await chromium.launch({
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });

  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });

  // Use light theme to prove high contrast AA
  await page.addInitScript(() => {
    try {
      localStorage.setItem(
        "hinaa_settings_v1",
        JSON.stringify({
          _version: 1,
          appearance: { theme: "light", motion: "system", avatarVisible: false },
          provider: { preferredMode: "mock" },
        })
      );
    } catch (e) {}
  });

  console.log("Navigating to http://127.0.0.1:5173/...");
  await page.goto("http://127.0.0.1:5173/", { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(1000);

  const textarea = page.locator("textarea").first();
  await textarea.waitFor({ timeout: 10000 });

  // Proof 1: "hello hina" — no card / no suggestion strip
  console.log("1. Typing 'hello hina'...");
  await textarea.fill("hello hina");
  await page.waitForTimeout(600);
  const path1 = path.join(OUT_DIR, "proof_hello_hina.png");
  await page.screenshot({ path: path1, fullPage: false });
  console.log(`Saved proof 1 to ${path1}`);

  // Proof 2: "remind me tomorrow at 8 to call Alex" — readable suggestion, Enter still sends
  console.log("2. Typing 'remind me tomorrow at 8 to call Alex'...");
  await textarea.fill("remind me tomorrow at 8 to call Alex");
  await page.waitForTimeout(600);
  const path2 = path.join(OUT_DIR, "proof_remind_suggestion.png");
  await page.screenshot({ path: path2, fullPage: false });
  console.log(`Saved proof 2 to ${path2}`);

  // Proof 2b: Adopt reminder card to prove contrast AA and title/time visibility
  console.log("2b. Adopting reminder card via Tab...");
  await textarea.press("Tab");
  await page.waitForTimeout(600);
  const path2b = path.join(OUT_DIR, "proof_remind_card_contrast.png");
  await page.screenshot({ path: path2b, fullPage: false });
  console.log(`Saved proof 2b to ${path2b}`);

  // Proof 3: "generate a red mug" — generating object
  console.log("3. Typing 'generate a red mug'...");
  await textarea.fill("generate a red mug");
  await page.waitForTimeout(600);
  console.log("Adopting image generation object via Tab...");
  await textarea.press("Tab");
  await page.waitForTimeout(600);
  const path3 = path.join(OUT_DIR, "proof_generate_red_mug.png");
  await page.screenshot({ path: path3, fullPage: false });
  console.log(`Saved proof 3 to ${path3}`);

  console.log("SUCCESS! All 3 proof screenshots captured.");
  await browser.close();
} catch (err) {
  console.error("Failed to capture screenshots:", err);
} finally {
  process.exit(0);
}
