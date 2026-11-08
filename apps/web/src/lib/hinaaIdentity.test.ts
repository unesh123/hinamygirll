import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

const calls: Array<{ url: string; headers: Headers }> = [];

beforeAll(async () => {
  vi.stubGlobal("fetch", vi.fn(async (resource: RequestInfo | URL, config?: RequestInit) => {
    const url = typeof resource === "string" ? resource : resource instanceof URL ? resource.toString() : resource.url;
    calls.push({ url, headers: new Headers(config?.headers) });
    return new Response("{}", { status: 200 });
  }));
  const { installLocalIdentityFetch } = await import("./hinaaIdentity");
  installLocalIdentityFetch();
});

afterEach(() => { calls.length = 0; });

describe("installLocalIdentityFetch", () => {
  it("adds the dev identity to Hina API calls made with plain fetch", async () => {
    await window.fetch("/v1/productivity/projects");
    await window.fetch("/api/goals", { method: "POST", headers: { "Content-Type": "application/json" } });
    expect(calls[0].headers.get("X-HINAA-Dev-User")).toBe("local-dev-user");
    expect(calls[1].headers.get("X-HINAA-Dev-User")).toBe("local-dev-user");
    expect(calls[1].headers.get("Content-Type")).toBe("application/json");
  });

  it("keeps a caller-provided identity and leaves non-API and cross-origin URLs untouched", async () => {
    await window.fetch("/v1/x", { headers: { "X-HINAA-Dev-User": "someone" } });
    await window.fetch("/models/hinaa.vrm");
    await window.fetch("https://example.com/v1/anything");
    expect(calls[0].headers.get("X-HINAA-Dev-User")).toBe("someone");
    expect(calls[1].headers.has("X-HINAA-Dev-User")).toBe(false);
    expect(calls[2].headers.has("X-HINAA-Dev-User")).toBe(false);
  });
});
