import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { NavigationRail } from "./NavigationRail";

const CAPABILITIES_URL = "/api/v1/capabilities";

function stubCapabilities(handler: (url: string) => Promise<Response>): void {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes(CAPABILITIES_URL)) return handler(url);
      return Promise.resolve(
        new Response(JSON.stringify({}), { status: 200, headers: { "Content-Type": "application/json" } })
      );
    })
  );
}

function renderRail(isOnline: boolean) {
  return render(<NavigationRail active="chat" onNavigate={() => {}} isOnline={isOnline} />);
}

describe("NavigationRail health status", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("reports the provider count measured from /v1/capabilities instead of a literal", async () => {
    stubCapabilities(async () =>
      new Response(
        JSON.stringify({
          runtime: { backendConnected: true, activeMode: "claude" },
          providers: [
            { id: "a", configured: true },
            { id: "b", configured: true },
            { id: "c", configured: false },
            { id: "d", configured: true },
          ],
          features: { memory: true, webSearch: false, artifacts: true },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );

    renderRail(true);

    await waitFor(() => expect(screen.getByText("3 providers · claude mode")).toBeInTheDocument());
    expect(screen.getByText("All systems nominal")).toBeInTheDocument();
    // Only the flags that are actually on read "Available".
    expect(screen.getAllByText("Available")).toHaveLength(2);
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
  });

  it("removes fake claude mode and All systems nominal line when hasClaudeAnswered is false", async () => {
    stubCapabilities(async () =>
      new Response(
        JSON.stringify({
          runtime: { backendConnected: true, activeMode: "claude" },
          providers: [
            { id: "a", configured: true },
            { id: "b", configured: true },
            { id: "c", configured: false },
          ],
          features: { memory: true, webSearch: false, artifacts: true },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );

    render(<NavigationRail active="chat" onNavigate={() => {}} isOnline={true} hasClaudeAnswered={false} />);

    await waitFor(() => expect(screen.getByText("Workspace ready")).toBeInTheDocument());
    expect(screen.getByText("2 providers · awaiting turn")).toBeInTheDocument();
    expect(screen.queryByText("All systems nominal")).not.toBeInTheDocument();
    expect(screen.queryByText(/claude mode/i)).not.toBeInTheDocument();
  });

  it("shows a degraded banner when the capabilities probe fails", async () => {
    stubCapabilities(async () => {
      throw new Error("network down");
    });

    renderRail(false);

    await waitFor(() =>
      expect(screen.getByTestId("rail-degraded-banner")).toBeInTheDocument()
    );
    expect(screen.getByText("Backend unreachable")).toBeInTheDocument();
  });

  it("never renders the fabricated uptime and node literals it replaced", async () => {
    stubCapabilities(async () => {
      throw new Error("network down");
    });

    const { container } = renderRail(false);

    await waitFor(() => expect(screen.getByTestId("rail-degraded-banner")).toBeInTheDocument());
    expect(container.textContent).not.toMatch(/99\.97/);
    expect(container.textContent).not.toMatch(/\d+ nodes/);
    expect(container.textContent).not.toMatch(/Synced/);
  });

  it("does not imply health while the probe is still in flight", () => {
    let resolveProbe: ((value: Response) => void) | null = null;
    stubCapabilities(
      () =>
        new Promise<Response>((resolve) => {
          resolveProbe = resolve;
        })
    );

    renderRail(true);

    expect(screen.getByText("Checking systems…")).toBeInTheDocument();
    expect(screen.queryByText("All systems nominal")).not.toBeInTheDocument();
    expect(resolveProbe).toBeTypeOf("function");
  });
});
