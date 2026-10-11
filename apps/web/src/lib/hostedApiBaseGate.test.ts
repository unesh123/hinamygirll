import { describe, expect, it } from "vitest";
import { execFileSync, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

// @ts-expect-error — plain .mjs build script, typed by its own exports
import { hostedApiBaseProblem } from "../../scripts/check-hosted-api-base.mjs";

const script = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../scripts/check-hosted-api-base.mjs");

describe("hostedApiBaseProblem", () => {
  it("passes a production build with an https backend", () => {
    expect(hostedApiBaseProblem("https://api.example.com", true)).toBeNull();
  });

  it("fails a production build with no backend", () => {
    expect(hostedApiBaseProblem("", true)).toMatch(/not set for a production build/);
  });

  it("fails a production build with a plain http backend", () => {
    expect(hostedApiBaseProblem("http://api.example.com", true)).toMatch(/must start with https/);
  });

  it("never fails a development build", () => {
    expect(hostedApiBaseProblem("", false)).toBeNull();
    expect(hostedApiBaseProblem("http://127.0.0.1:8000", false)).toBeNull();
  });
});

describe("check-hosted-api-base command", () => {
  it("exits non-zero for a production build with no backend", () => {
    const result = spawnSync(process.execPath, [script, "--production"], {
      env: { ...process.env, VITE_HINAA_API_BASE_URL: "" },
      encoding: "utf8",
    });
    expect(result.status).toBe(1);
    expect(result.stderr).toMatch(/not set/);
  });

  it("prints OK when the hosted backend is configured", () => {
    const out = execFileSync(process.execPath, [script, "--production"], {
      env: { ...process.env, VITE_HINAA_API_BASE_URL: "https://api.example.com" },
      encoding: "utf8",
    });
    expect(out).toMatch(/OK/);
  });
});
