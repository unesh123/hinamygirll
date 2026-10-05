import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useCapabilities } from "./useCapabilities";

afterEach(() => vi.unstubAllGlobals());

describe("capability connectivity", () => {
  it("clears the connected badge after discovery fails and recovers when online", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ models: [], providers: [] }) });
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(useCapabilities);
    await waitFor(() => expect(result.current.runtime.backendConnected).toBe(true));
    fetchMock.mockRejectedValue(new Error("offline"));
    await act(async () => { await result.current.refetch(); });
    expect(result.current.runtime.backendConnected).toBe(false);
    expect(result.current.error).toContain("offline");
    fetchMock.mockResolvedValue({ ok: true, json: async () => ({ models: [], providers: [] }) });
    await act(async () => { await result.current.refetch(); });
    expect(result.current.runtime.backendConnected).toBe(true);
    expect(result.current.error).toBeNull();
  });
});
