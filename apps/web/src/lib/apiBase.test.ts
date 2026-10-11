import { describe, expect, it } from "vitest";

import { resolveApiBase } from "./apiBase";

describe("resolveApiBase", () => {
  it("uses a configured https backend and strips trailing slashes", () => {
    expect(resolveApiBase("https://api.example.com//", true)).toEqual({
      kind: "configured",
      base: "https://api.example.com",
    });
  });

  it("allows relative calls in development when nothing is configured", () => {
    expect(resolveApiBase("", false)).toEqual({ kind: "relative-dev" });
    expect(resolveApiBase(undefined, false)).toEqual({ kind: "relative-dev" });
  });

  it("reports a missing backend on the hosted site instead of failing silently", () => {
    const status = resolveApiBase("", true);
    expect(status.kind).toBe("relative-production");
    if (status.kind === "relative-production") {
      expect(status.reason).toContain("No API base URL is set");
    }
  });

  it("refuses a plain http backend on the hosted site", () => {
    const status = resolveApiBase("http://api.example.com", true);
    expect(status.kind).toBe("relative-production");
    if (status.kind === "relative-production") {
      expect(status.reason).toContain("https://");
    }
  });

  it("accepts http in development so local testing still works", () => {
    expect(resolveApiBase("http://127.0.0.1:8000", false)).toEqual({
      kind: "configured",
      base: "http://127.0.0.1:8000",
    });
  });
});
