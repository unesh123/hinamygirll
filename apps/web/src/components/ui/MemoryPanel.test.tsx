import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryPanel } from "./MemoryPanel";

/** The page a Cloudflare quick tunnel serves once uvicorn stops answering. */
const EDGE_HTML = `<!DOCTYPE html>
<html lang="en-US"><head><title>530: Web server is returning an unknown error</title></head>
<body><div class="cf-error-details"><h1>Error code 530</h1>
<span>Cloudflare Ray ID: <strong>7f3a</strong></span></div></body></html>`;

function edgeResponse(status: number): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "text/html; charset=UTF-8" }),
    text: async () => EDGE_HTML,
    json: async () => {
      throw new SyntaxError("Unexpected token '<', \"<!doctype\" is not valid JSON");
    },
  } as Response;
}

afterEach(() => vi.unstubAllGlobals());

describe("MemoryPanel failure surface", () => {
  it("reads the edge failure as one sentence with no markup in it", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(edgeResponse(530)));

    render(<MemoryPanel isOpen onClose={() => {}} />);

    const line = await screen.findByText(/network edge returned HTTP 530/);
    expect(line.textContent).toBe(
      "HINAA's backend did not answer — the network edge returned HTTP 530 instead of her.",
    );
    expect(line.textContent).not.toContain("<");
    expect(line.textContent!.toLowerCase()).not.toContain("cloudflare");
  });

  it("does not show an empty-store message while the store is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(edgeResponse(200)));

    render(<MemoryPanel isOpen onClose={() => {}} />);

    await screen.findByText(/answered with a web page instead of its own response/);
    expect(
      screen.queryByText(/No local memories stored yet/),
    ).toBeNull();
  });
});
