import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import useMemory from "./useMemory";

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

describe("useMemory failure reporting", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("keeps the backend reason when the store refuses the read", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(401, {
          code: "AUTH_REQUIRED",
          message: "This HINAA instance is reachable from the internet.",
        }),
      ),
    );

    const { result } = renderHook(() => useMemory());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.entries).toEqual([]);
    expect(result.current.error).toBe("This HINAA instance is reachable from the internet.");
  });

  it("reports a status when the refusal carries no message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(500, {})));

    const { result } = renderHook(() => useMemory());
    await waitFor(() => expect(result.current.error).toBeTruthy());

    expect(result.current.error).toContain("500");
  });

  it("clears the reason once a read succeeds", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { message: "closed" }))
      .mockResolvedValue(jsonResponse(200, { memories: [] }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useMemory());
    await waitFor(() => expect(result.current.error).toBe("closed"));

    await act(async () => {
      await result.current.fetchMemories();
    });

    expect(result.current.error).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
