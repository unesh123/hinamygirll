import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { buildCommands, filterCommands } from "../commands";
import { ShellRoutes } from "../ShellApp";
import NewsPage from "./NewsPage";

vi.mock("../../App", () => ({ default: () => <div>legacy app</div> }));

type Json = Record<string, unknown>;
interface Call { method: string; path: string; body: Json | null }

const WATCH = { id: "w1", name: "Nepal economy", topics: ["Nepal"], keywords: [], sources: ["https://feeds.example.com/rss"], cadence: "daily", dailyHour: 8, enabled: true, lastRunAt: null, nextRunAt: "2026-11-09T02:15:00+00:00" };
const DIGEST = {
  id: "d1", watchlistId: "w1", title: "Nepal economy — 08 Nov 11:45 NPT", generatedBy: "extractive", articleCount: 2, createdAt: "2026-11-08T06:00:00+00:00",
  items: [{ text: "Central bank cuts policy rate", urls: ["https://www.example.com/a", "https://b.example.org/x"] }],
  sources: ["https://www.example.com/a", "https://b.example.org/x"],
};
const CONNECTIONS = [
  { id: "youtube", name: "YouTube", status: "ready", connected: false, account: "", requirements: "" },
  { id: "instagram", name: "Instagram", status: "requires_setup", connected: false, account: "", requirements: "Needs a Business account and Meta App Review." },
];

interface Fixture { watchlists: Json[]; digests: Json[]; failDigests?: boolean; missing?: boolean }

function mockApi(fx: Fixture): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost");
    const method = init?.method ?? "GET";
    calls.push({ method, path: url.pathname, body: init?.body ? (JSON.parse(String(init.body)) as Json) : null });
    const reply = (body: unknown, status = 200) =>
      Promise.resolve({ ok: status < 400, status, json: () => (status === 204 ? Promise.reject(new Error("no body")) : Promise.resolve(body)) } as Response);
    if (fx.missing) return reply({}, 404);
    if (method === "POST" && url.pathname.endsWith("/run")) return reply({ digest: DIGEST, warnings: ["Feed https://x failed: timeout"], deliveries: [] });
    if (method === "POST" && url.pathname.endsWith("/watchlists")) return reply({ ...WATCH, id: "w2" }, 201);
    if (method === "DELETE") return reply(null, 204);
    if (url.pathname.endsWith("/watchlists")) return reply({ items: fx.watchlists, total: fx.watchlists.length });
    if (url.pathname.endsWith("/digests")) return fx.failDigests ? reply({ message: "boom" }, 500) : reply({ items: fx.digests, total: fx.digests.length });
    if (url.pathname.endsWith("/connections")) return reply({ items: CONNECTIONS });
    if (url.pathname.endsWith("/youtube/connect")) return reply({ authUrl: "https://accounts.google.com/o/oauth2/v2/auth?x=1" });
    return reply({}, 404);
  }));
  return calls;
}

beforeEach(() => vi.unstubAllGlobals());
afterEach(() => vi.unstubAllGlobals());

describe("News page states", () => {
  it("shows loading first", async () => {
    mockApi({ watchlists: [WATCH], digests: [DIGEST] });
    render(<NewsPage />);
    expect(screen.getByText("Loading watchlists…")).toBeInTheDocument();
    expect(screen.getByText("Loading digests…")).toBeInTheDocument();
    await screen.findByRole("article");
  });

  it("shows empty states", async () => {
    mockApi({ watchlists: [], digests: [] });
    render(<NewsPage />);
    expect(await screen.findByText("No watchlists yet.")).toBeInTheDocument();
    expect(await screen.findByText("No digests yet.")).toBeInTheDocument();
  });

  it("shows data with a source link for every digest bullet", async () => {
    mockApi({ watchlists: [WATCH], digests: [DIGEST] });
    render(<NewsPage />);
    const digest = await screen.findByRole("article", { name: DIGEST.title });
    expect(within(digest).getByText("Central bank cuts policy rate")).toBeInTheDocument();
    const link = within(digest).getByRole("link", { name: "example.com" });
    expect(link).toHaveAttribute("href", "https://www.example.com/a");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(within(digest).getByRole("link", { name: "b.example.org" })).toBeInTheDocument();
    expect(await screen.findByText("Nepal economy")).toBeInTheDocument();
    expect(screen.getByText("Instagram")).toBeInTheDocument();
    expect(screen.getByText("Requires setup")).toBeInTheDocument();
  });

  it("shows an error with retry when digests fail to load", async () => {
    mockApi({ watchlists: [WATCH], digests: [], failDigests: true });
    render(<NewsPage />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Couldn’t load digests");
    expect(within(alert).getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("says when the backend has no news endpoint", async () => {
    mockApi({ watchlists: [], digests: [], missing: true });
    render(<NewsPage />);
    expect(await screen.findByText(/watchlists endpoint isn’t available/)).toBeInTheDocument();
  });
});

describe("News page actions", () => {
  it("runs a watchlist now, reports warnings and refetches digests", async () => {
    const calls = mockApi({ watchlists: [WATCH], digests: [] });
    render(<NewsPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Run Nepal economy now" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Digest ready: 1 cited stories.");
    expect(screen.getByRole("status")).toHaveTextContent("Feed https://x failed: timeout");
    expect(calls.some((c) => c.method === "POST" && c.path === "/v1/news/watchlists/w1/run")).toBe(true);
    await waitFor(() => expect(calls.filter((c) => c.path === "/v1/news/digests").length).toBeGreaterThan(1));
  });

  it("validates and creates a watchlist", async () => {
    const calls = mockApi({ watchlists: [], digests: [] });
    render(<NewsPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Add watchlist" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Give the watchlist a name.");
    await userEvent.type(screen.getByLabelText("Name"), "AI");
    await userEvent.click(screen.getByRole("button", { name: "Add watchlist" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Add at least one topic");
    await userEvent.type(screen.getByLabelText("Topics (comma separated)"), "AI, robotics");
    await userEvent.click(screen.getByRole("button", { name: "Add watchlist" }));
    await waitFor(() => expect(calls.find((c) => c.method === "POST" && c.path === "/v1/news/watchlists")?.body).toMatchObject({ name: "AI", topics: ["AI", "robotics"], cadence: "daily", dailyHour: 8 }));
  });

  it("Connect YouTube opens the Google consent URL", async () => {
    mockApi({ watchlists: [], digests: [] });
    const open = vi.fn();
    vi.stubGlobal("open", open);
    render(<NewsPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Connect YouTube" }));
    await waitFor(() => expect(open).toHaveBeenCalledWith("https://accounts.google.com/o/oauth2/v2/auth?x=1", "_blank", "noopener"));
  });
});

describe("News route and palette", () => {
  it("is registered in the command palette and as /news", async () => {
    const commands = buildCommands(() => undefined, "/");
    expect(filterCommands(commands, "news").some((c) => c.label.includes("News"))).toBe(true);
    mockApi({ watchlists: [WATCH], digests: [DIGEST] });
    render(
      <MemoryRouter initialEntries={["/news"]}>
        <ShellRoutes />
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { name: "News" })).toBeInTheDocument();
  });
});
