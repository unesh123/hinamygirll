import { defineConfig, devices } from "@playwright/test";

// The API webserver command must work both locally (Windows venv) and in CI
// (Linux system Python). Override via HINAA_API_CMD when a custom interpreter
// is needed (e.g. a CI venv).
function apiServerCommand(): string {
  if (process.env.HINAA_API_CMD) {
    return process.env.HINAA_API_CMD;
  }
  if (process.platform === "win32") {
    return "..\\api\\.venv\\Scripts\\python.exe -m uvicorn hinaa_api.main:app --app-dir ..\\api --host 127.0.0.1 --port 8000";
  }
  return "python -m uvicorn hinaa_api.main:app --app-dir ../api --host 127.0.0.1 --port 8000";
}

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  // Cap workers: the suite also builds the app and boots the API backend, so
  // unbounded parallelism CPU-starves the machine and multi-step tests blow
  // the 30s default timeout (observed locally on Windows, dev backend on
  // :8000 being reused). 3 workers keeps it fast and stable on both 2-vCPU CI
  // runners and local dev machines.
  workers: 3,
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
      command: apiServerCommand(),
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
