import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import IntegrationsPage from "./IntegrationsPage";

type Route = { status?: number; body?: unknown; reject?: boolean };

function mockApi(routes: Record<string, Route>) {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    const path = String(input);
    const route = routes[path] ?? { status: 404 };
    if (route.reject) return Promise.reject(new Error("offline"));
    const status = route.status ?? 200;
    return Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(route.body ?? {}) } as Response);
  }));
}

beforeEach(() => vi.unstubAllGlobals());
afterEach(() => vi.unstubAllGlobals());

describe("Integrations hub", () => {
  it("shows configured / not-configured connectors, searchable skills, MCP servers and tools", async () => {
    mockApi({
      "/v1/integrations": { body: { integrations: [
        { service_id: "github", display_name: "GitHub", category: "developer", connected: true, status_text: "Token set", capabilities: ["pr"] },
        { service_id: "notion", display_name: "Notion", category: "docs", connected: false, status_text: "No key", capabilities: [] },
      ] } },
      "/v1/skills": { body: { skills: [
        { id: "s1", name: "Summarize PDF", description: "Digest long documents", category: "docs" },
        { id: "s2", name: "Deploy site", description: "Ship to Vercel", category: "dev" },
      ] } },
      "/v1/mcp/servers": { body: [{ name: "filesystem", status: "connected", tool_count: 7, transport: "stdio" }] },
      "/v1/tools": { body: [{ name: "web_search", displayName: "Web search", description: "Search the web", riskLevel: "low", requiresConfirmation: false }] },
    });
    render(<IntegrationsPage />);

    const connectors = await screen.findByRole("list", { name: "Connectors" });
    expect(within(connectors).getByText("Configured")).toBeInTheDocument();
    expect(within(connectors).getByText("Not configured")).toBeInTheDocument();
    expect(screen.getByText(/1\/2 configured/)).toBeInTheDocument();

    const skills = await screen.findByRole("list", { name: "Skills" });
    expect(within(skills).getAllByRole("listitem")).toHaveLength(2);
    await userEvent.type(screen.getByRole("searchbox", { name: "Search skills" }), "vercel");
    expect(within(screen.getByRole("list", { name: "Skills" })).getAllByRole("listitem")).toHaveLength(1);
    await userEvent.clear(screen.getByRole("searchbox", { name: "Search skills" }));
    await userEvent.type(screen.getByRole("searchbox", { name: "Search skills" }), "nothing-like-this");
    expect(screen.getByText(/No skills match/)).toBeInTheDocument();

    expect(await screen.findByText("filesystem")).toBeInTheDocument();
    expect(screen.getByText("7 tools")).toBeInTheDocument();
    expect(await screen.findByText("Web search")).toBeInTheDocument();
  });

  it("falls back to /v1/integrations/status when /v1/integrations is absent", async () => {
    mockApi({
      "/v1/integrations/status": { body: { integrations: [{ service_id: "outlook", display_name: "Outlook", category: "mail", connected: false, status_text: "", capabilities: [] }] } },
    });
    render(<IntegrationsPage />);
    expect(await screen.findByText("Outlook")).toBeInTheDocument();
    expect(screen.getByText("Not configured")).toBeInTheDocument();
  });

  it("shows graceful 'not available' states when endpoints 404", async () => {
    mockApi({});
    render(<IntegrationsPage />);
    expect(await screen.findByText(/connectors endpoint isn’t available/)).toBeInTheDocument();
    expect(await screen.findByText(/skills endpoint isn’t available/)).toBeInTheDocument();
    expect(await screen.findByText(/MCP servers endpoint isn’t available/)).toBeInTheDocument();
  });

  it("shows an error with retry when the network fails", async () => {
    mockApi({ "/v1/mcp/servers": { reject: true } });
    render(<IntegrationsPage />);
    const alert = await screen.findByText(/Couldn’t load MCP servers/);
    expect(alert).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Retry" }).length).toBeGreaterThan(0);
  });

  it("shows an empty state when the endpoint returns nothing", async () => {
    mockApi({ "/v1/integrations": { body: { integrations: [] } }, "/v1/skills": { body: [] } });
    render(<IntegrationsPage />);
    expect(await screen.findByText("No connectors yet.")).toBeInTheDocument();
    expect(await screen.findByText("No skills yet.")).toBeInTheDocument();
  });
});
