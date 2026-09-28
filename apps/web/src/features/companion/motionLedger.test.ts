import { describe, expect, it, vi, afterEach } from "vitest";
import { MOTION_LEDGER_ENDPOINT, recordMotionState } from "./motionLedger";

describe("recordMotionState", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("posts the state to the ledger endpoint", () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);

    recordMotionState("idle", "reply delivered");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(MOTION_LEDGER_ENDPOINT);
    expect(init.method).toBe("POST");
    expect(init.keepalive).toBe(true);
    const body = JSON.parse(String(init.body));
    expect(body.state).toBe("idle");
    expect(body.detail).toBe("reply delivered");
  });

  it("omits a missing detail as null rather than undefined", () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);

    recordMotionState("thinking");

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body)).detail).toBeNull();
  });

  it("never throws when the ledger is unreachable", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("backend down")),
    );
    expect(() => recordMotionState("speaking")).not.toThrow();
  });

  it("never throws when fetch itself is unavailable", () => {
    vi.stubGlobal("fetch", undefined);
    expect(() => recordMotionState("idle")).not.toThrow();
  });
});
