import { describe, expect, it } from "vitest";
import { chooseRealtimeTarget } from "./realtimeSocketTarget";

const base = { pageHost: "hinaa-workspace.vercel.app", isHttps: true, sameOriginUrl: "wss://hinaa-workspace.vercel.app/api/v1/realtime" };

describe("chooseRealtimeTarget", () => {
  it("does not open the dead same-origin socket when the backend says it is unavailable", () => {
    const target = chooseRealtimeTarget({ ...base, advertisedUrl: null, answered: true });
    expect(target.kind).toBe("unavailable");
    if (target.kind === "unavailable") expect(target.reason).toContain("no realtime address");
  });

  it("uses an advertised wss origin on a different host", () => {
    const target = chooseRealtimeTarget({ ...base, advertisedUrl: "wss://api.example.com/v1/realtime", answered: true });
    expect(target).toEqual({ kind: "advertised", url: "wss://api.example.com/v1/realtime" });
  });

  it("refuses an advertised origin that points back at the page host", () => {
    const target = chooseRealtimeTarget({ ...base, advertisedUrl: "wss://hinaa-workspace.vercel.app/v1/realtime", answered: true });
    expect(target.kind).toBe("same-origin");
  });

  it("falls back to same-origin when the backend could not be asked", () => {
    const target = chooseRealtimeTarget({ ...base, advertisedUrl: null, answered: false });
    expect(target).toEqual({ kind: "same-origin", url: base.sameOriginUrl });
  });

  it("always uses same-origin on plain http (local development)", () => {
    const target = chooseRealtimeTarget({ ...base, isHttps: false, advertisedUrl: null, answered: true });
    expect(target).toEqual({ kind: "same-origin", url: base.sameOriginUrl });
  });
});
