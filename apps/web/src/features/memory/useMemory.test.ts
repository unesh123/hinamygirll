import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import useMemory from "./useMemory";

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as Response;
}

/** What a dead quick tunnel puts on the wire: an edge page, sometimes at 200. */
const EDGE_HTML = `<!DOCTYPE html>
<html><head><title>530: Web server is returning an unknown error</title></head>
<body><div class="cf-error-details">Cloudflare Ray ID: <strong>deadbeef</strong></div></body></html>`;

function edgeHtmlResponse(status: number): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "text/html; charset=UTF-8" }),
    json: async () => {
      throw new SyntaxError("Unexpected token '<'");
    },
    text: async () => EDGE_HTML,
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

  it("names the edge instead of quoting its page", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(edgeHtmlResponse(530)));

    const { result } = renderHook(() => useMemory());
    await waitFor(() => expect(result.current.error).toBeTruthy());

    const line = result.current.error!;
    expect(line).toContain("530");
    expect(line).not.toContain("<");
    expect(line.toLowerCase()).not.toContain("cloudflare");
    expect(line.split("\n")).toHaveLength(1);
  });

  it("treats an HTML 200 as the edge answering, not as JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(edgeHtmlResponse(200)));

    const { result } = renderHook(() => useMemory());
    await waitFor(() => expect(result.current.error).toBeTruthy());

    const line = result.current.error!;
    expect(line).toContain("200");
    expect(line).not.toContain("Unexpected token");
    expect(line).not.toContain("<");
  });

  it("says which layer failed when no response arrived at all", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );

    const { result } = renderHook(() => useMemory());
    await waitFor(() => expect(result.current.error).toBeTruthy());

    expect(result.current.error).toBe(
      "HINAA's memory store never answered — Failed to fetch.",
    );
  });
});
