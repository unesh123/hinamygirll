import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchProviderStatuses, reprobeCxGateway } from "../../audio/api";
import type { ProviderStatus } from "../../audio/api";
import { useProviders } from "./useProviders";

vi.mock("../../audio/api", () => ({ fetchProviderStatuses: vi.fn(), reprobeCxGateway: vi.fn() }));
const fetchStatuses = vi.mocked(fetchProviderStatuses);
const statuses: ProviderStatus[] = [
  { id: "groq", state: "healthy", capabilities: ["model:groq-configured", "default-model:groq-configured"], userMessage: "Answered" },
  { id: "experiential", state: "untested", capabilities: ["model:exp-configured", "default-model:exp-configured"], userMessage: "Configured" },
  { id: "local", state: "degraded", capabilities: ["llm"], userMessage: "No local voice" },
];

async function flush() { await act(async () => { await Promise.resolve(); }); }
function visibility(value: "hidden" | "visible") {
  Object.defineProperty(document, "visibilityState", { configurable: true, value });
  act(() => document.dispatchEvent(new Event("visibilitychange")));
}

describe("provider health polling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(Math, "random").mockReturnValue(0.5);
    vi.clearAllMocks();
    fetchStatuses.mockReset();
    fetchStatuses.mockResolvedValue(statuses);
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
  });
  afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

  it("discovers every configured brain and preserves reported local degradation", async () => {
    const { result } = renderHook(useProviders);
    expect(result.current.getHealth("groq")).toBe("checking");
    await flush();
    expect(result.current.getDefaultModel("experiential")).toBe("exp-configured");
    expect(result.current.getModelOptions("groq")[0].id).toBe("groq-configured");
    expect(result.current.getHealth("local")).toBe("degraded");
    expect(result.current.providerOptions.some((p) => p.mode === "experiential")).toBe(true);
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(fetchStatuses).toHaveBeenCalledTimes(2);
  });

  it("ignores late failures from a request replaced by refresh", async () => {
    let failOld!: (error: Error) => void;
    fetchStatuses.mockImplementationOnce(() => new Promise((_, reject) => { failOld = reject; }));
    const { result } = renderHook(useProviders);
    act(() => result.current.refresh());
    await flush();
    await act(async () => { failOld(new Error("old request failed")); });
    expect(result.current.error).toBeNull();
    expect(result.current.getHealth("groq")).toBe("healthy");
  });

  it("does not advertise stale cloud or local availability after the backend goes offline", async () => {
    const { result } = renderHook(useProviders);
    await flush();
    fetchStatuses.mockRejectedValue(new Error("backend offline"));
    act(() => result.current.refresh());
    await flush();
    expect(result.current.getHealth("groq")).toBe("unavailable");
    expect(result.current.getHealth("local")).toBe("unavailable");
    expect(result.current.getHealth("mock")).toBe("healthy");
    expect(result.current.providerOptions.find((p) => p.mode === "groq")?.available).toBe(false);
  });

  it("times out a hung request and recovers through bounded backoff", async () => {
    fetchStatuses.mockImplementationOnce((signal) => new Promise((_, reject) => {
      signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    }));
    const { result } = renderHook(useProviders);
    await act(async () => { await vi.advanceTimersByTimeAsync(15_000); });
    expect(result.current.loaded).toBe(true);
    expect(result.current.error).toContain("retrying in 2s");
    await act(async () => { await vi.advanceTimersByTimeAsync(2_000); });
    expect(result.current.error).toBeNull();
    expect(result.current.getHealth("groq")).toBe("healthy");
  });

  it("pauses all polling while hidden and refreshes on return", async () => {
    renderHook(useProviders);
    await flush();
    visibility("hidden");
    await act(async () => { await vi.advanceTimersByTimeAsync(120_000); });
    expect(fetchStatuses).toHaveBeenCalledTimes(1);
    visibility("visible");
    await flush();
    expect(fetchStatuses).toHaveBeenCalledTimes(2);
  });

  it("aborts on unmount without starting another request", async () => {
    const { unmount } = renderHook(useProviders);
    await flush();
    const signal = fetchStatuses.mock.calls[0][0];
    unmount();
    expect(signal?.aborted).toBe(true);
    await act(async () => { await vi.advanceTimersByTimeAsync(120_000); });
    expect(fetchStatuses).toHaveBeenCalledTimes(1);
  });

  it("waits for refreshed statuses before reporting reprobe completion", async () => {
    vi.mocked(reprobeCxGateway).mockResolvedValue({} as Awaited<ReturnType<typeof reprobeCxGateway>>);
    const { result } = renderHook(useProviders);
    await flush();
    let finish!: (value: ProviderStatus[]) => void;
    fetchStatuses.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
    let complete = false;
    let reprobe!: Promise<void>;
    await act(async () => { reprobe = result.current.reprobeCx!().then(() => { complete = true; }); });
    expect(complete).toBe(false);
    await act(async () => { finish(statuses); await reprobe; });
    expect(complete).toBe(true);
  });
});
