import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { installDevIdentityFetch } from "./devIdentityFetch";

describe("installDevIdentityFetch", () => {
  const original = window.fetch;
  const spy = vi.fn(async () => new Response("{}"));
  let restore: () => void;

  beforeEach(() => {
    spy.mockClear();
    window.fetch = spy as unknown as typeof fetch;
    restore = installDevIdentityFetch("https://api.example.com/");
  });
  afterEach(() => {
    restore();
    window.fetch = original;
  });

  const sentHeaders = () => new Headers((spy.mock.calls[0] as unknown[])[1] as RequestInit | undefined ? ((spy.mock.calls[0] as unknown[])[1] as RequestInit).headers : undefined);

  it("adds the dev identity to same-origin API calls", async () => {
    await window.fetch("/v1/tasks");
    expect(sentHeaders().get("X-HINAA-Dev-User")).toBe("local-dev-user");
  });

  it("adds it to the configured API origin", async () => {
    await window.fetch("https://api.example.com/api/v1/tools");
    expect(sentHeaders().get("X-HINAA-Dev-User")).toBe("local-dev-user");
  });

  it("keeps an explicit identity and other headers", async () => {
    await window.fetch("/api/v1/x", { headers: { "X-HINAA-Dev-User": "someone", "Content-Type": "application/json" } });
    expect(sentHeaders().get("X-HINAA-Dev-User")).toBe("someone");
    expect(sentHeaders().get("Content-Type")).toBe("application/json");
  });

  it("leaves third-party and non-API requests untouched", async () => {
    await window.fetch("https://other.example.com/v1/tasks");
    await window.fetch("/models/hina.vrm");
    for (const call of spy.mock.calls as unknown[][]) expect(call[1]).toBeUndefined();
  });
});
