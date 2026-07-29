import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: true,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "pixel-5", use: { ...devices["Pixel 5"] } },
    {
      name: "small-android",
      use: {
        viewport: { width: 320, height: 568 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
  webServer: [
    {
      command:
        "..\\api\\.venv\\Scripts\\python.exe -m uvicorn hinaa_api.main:app --app-dir ..\\api --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/health/live",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: "pnpm build && pnpm preview --host 127.0.0.1 --port 4173",
      url: "http://127.0.0.1:4173",
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
